"""Automatically supervised by FastAPI; python -m app.worker remains available for deployment."""
from datetime import timedelta
from contextlib import contextmanager
from hashlib import sha256
from pathlib import PurePosixPath
from threading import Thread, Event
import logging
import mimetypes
import re
import time
from sqlalchemy import select
from app.common.assets import asset_url
from app.core.config import get_settings
from app.core.database import build_database
from app.core.errors import BusinessError, require
from app.models.entities import (ImportJob, IndexTask, KnowledgeUnit, Attachment, Chunk, User,
                                UnitPermission, utcnow, new_id)
from app.integrations.infrastructure import Infrastructure
from app.integrations.parser import parse_document
from app.services.identity import IdentityService
from app.services.knowledge import KnowledgeService
from app.services.settings import IntegrationService
from app.services.image_analysis import DocumentImageAnalyzer
from app.repositories.jobs import JobRepository, Claim
from app.workflows.ingestion import import_graph, index_graph, ImportState, IndexState

log = logging.getLogger(__name__)


def safe_error(exc, prefix):
    return exc.detail[:1000] if isinstance(exc, BusinessError) else prefix+'（'+type(exc).__name__+'）'


class Worker:
    def __init__(self, settings, factory, infrastructure):
        self.settings, self.factory, self.infra = settings, factory, infrastructure
        self.last_mining = 0
        self.import_graph = import_graph(self.load_document, self.parse_import, self.analyze_images, self.persist_document)
        self.index_graph = index_graph(self.load_chunks, self.embed_chunks, self.write_vectors, self.finish_index)

    def claim(self, model):
        with self.factory.begin() as db:
            return JobRepository(db, self.settings).claim(model)

    @contextmanager
    def heartbeat(self, model, claim):
        stop = Event()
        def renew():
            while not stop.wait(min(30, max(0.2, self.settings.worker_lease_seconds/3))):
                try:
                    with self.factory.begin() as db:
                        if not JobRepository(db, self.settings).renew(model, claim):
                            return
                except Exception:
                    # A failed heartbeat cannot grant ownership; fenced checkpoints will refuse stale writes.
                    return
        thread = Thread(target=renew, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=1)

    def process_import(self, claim):
        with self.heartbeat(ImportJob, claim):
            self._process_import(claim)

    def _process_import(self, claim):
        try:
            self.import_graph.invoke({'task_id': claim.id, 'generation': claim.generation})
        except Exception as exc:
            with self.factory.begin() as db:
                job = JobRepository(db, self.settings).owned(ImportJob, claim)
                if job is None or job.unit_id:
                    return
                job.error = safe_error(exc, '导入处理失败')
                job.status, job.lease_until = 'failed', None

    def load_document(self, state: ImportState):
        claim = Claim(state['task_id'], state['generation'])
        with self.factory.begin() as db:
            job = JobRepository(db, self.settings).owned(ImportJob, claim)
            if job is None or job.unit_id:
                return {'proceed': False}
            if job.cancel_requested:
                job.status, job.lease_until = 'canceled', None
                return {'proceed': False}
            owner = db.get(User, job.owner_id)
            require(owner and owner.status == 'active', '导入账号已停用', 403)
            IdentityService(db, self.settings).identity(owner).need('knowledge.import')
            attachment = db.get(Attachment, job.attachment_id)
            job.phase = 1
            return {'proceed': True, 'file_name': attachment.file_name, 'object_key': attachment.object_key}

    def parse_import(self, state: ImportState):
        claim = Claim(state['task_id'], state['generation'])
        with self.factory.begin() as db:
            job = JobRepository(db, self.settings).owned(ImportJob, claim)
            if job is None:
                return {'proceed': False}
            if job.cancel_requested:
                job.status, job.lease_until = 'canceled', None
                return {'proceed': False}
            config = IntegrationService(db, self.settings).effective('mineru')
        log.info('Import %s: parse_document (%s)', claim.id,
                 'MinerU' if state['file_name'].lower().endswith(('.pdf', '.doc')) else 'local')
        parsed = parse_document(state['file_name'], self.infra.storage.get(state['object_key']), config)
        require(bool(parsed.body.strip()), '未解析到有效文档正文')
        require(len(parsed.body) <= 2_000_000, '解析正文超过 200 万字符限制')
        with self.factory.begin() as db:
            job = JobRepository(db, self.settings).owned(ImportJob, claim)
            if job is None:
                return {'proceed': False}
            if job.cancel_requested:
                job.status, job.lease_until = 'canceled', None
                return {'proceed': False}
        return {'proceed': True, 'parsed': parsed}

    def analyze_images(self, state: ImportState):
        claim = Claim(state['task_id'], state['generation'])

        def active():
            with self.factory.begin() as db:
                job = JobRepository(db, self.settings).owned(ImportJob, claim)
                if job is None:
                    return False
                if job.cancel_requested:
                    job.status, job.lease_until = 'canceled', None
                    return False
                return True

        if not active():
            return {'proceed': False}
        parsed = state['parsed']
        if parsed.images:
            with self.factory() as db:
                config = IntegrationService(db, self.settings).effective('llm')
            if config['enabled'] and config.get('vision_enabled'):
                log.info('Import %s: analyze_images (%d images)', claim.id, len(parsed.images))
                parsed = DocumentImageAnalyzer(config).enrich(parsed, active)
                if parsed is None:
                    return {'proceed': False}
        with self.factory.begin() as db:
            job = JobRepository(db, self.settings).owned(ImportJob, claim)
            if job is None:
                return {'proceed': False}
            if job.cancel_requested:
                job.status, job.lease_until = 'canceled', None
                return {'proceed': False}
            job.phase = 2
        return {'proceed': True, 'parsed': parsed}

    def persist_document(self, state: ImportState):
        claim = Claim(state['task_id'], state['generation'])
        parsed, name = state['parsed'], state['file_name']
        body = parsed.body
        with self.factory.begin() as db:
            job = JobRepository(db, self.settings).owned(ImportJob, claim)
            if job is None or job.unit_id:
                return {'proceed': False}
            if job.cancel_requested:
                job.status, job.lease_until = 'canceled', None
                return {'proceed': False}
            attachment = db.get(Attachment, job.attachment_id)
            unit = KnowledgeUnit(unit_code='KB-'+new_id().replace('-', '')[:16].upper(),
                title=name.rsplit('.', 1)[0], content=body, summary=body[:300],
                source_file_name=name, file_type=name.rsplit('.', 1)[-1].lower(),
                file_size=attachment.size, creator_id=job.owner_id, status='draft')
            db.add(unit)
            db.flush()
            if parsed.images:
                body = self._store_images(db, unit, job.owner_id, body, parsed.images)
                unit.content, unit.summary = body, body[:300]
            KnowledgeService(db, self.settings).rebuild_chunks(unit, job.owner_id)
            attachment.unit_id = unit.id
            job.unit_id, job.phase, job.lease_until = unit.id, 3, None
            log.info('Import %s: document and chunks saved; index queued', claim.id)
            return {'proceed': True, 'unit_id': unit.id}

    def _store_images(self, db, unit, owner_id, body, images):
        """Persist MinerU figures in MinIO and swap relative links for signed asset URLs."""
        for rel, data in images.items():
            name = PurePosixPath(rel).name
            name = (re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('._') or 'image')[-120:]
            mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            object_key = 'images/'+unit.id+'/'+new_id()+'-'+name
            self.infra.storage.put(object_key, data, mime)
            a = Attachment(unit_id=unit.id, uploader_id=owner_id, file_name=name, object_key=object_key,
                           bucket=self.settings.minio_bucket, mime_type=mime, size=len(data),
                           sha256=sha256(data).hexdigest())
            db.add(a)
            db.flush()
            url = asset_url(self.settings, a.id)
            body = body.replace('./'+rel, url).replace(rel, url)
        return body

    def cancel_import_index(self, db, unit, task):
        jobs = list(db.scalars(select(ImportJob).where(ImportJob.unit_id == unit.id,
                                                     ImportJob.cancel_requested.is_(True))))
        if not jobs:
            return False
        # Do not discard knowledge deliberately edited/published/authorized by a concurrent administrator.
        fresh = unit.current_version == 1 and unit.status == 'draft' and not db.scalar(
            select(UnitPermission.id).where(UnitPermission.unit_id == unit.id))
        for job in jobs:
            job.status, job.lease_until = 'canceled', None
        if not fresh:
            return False
        unit.deleted_at, unit.index_status = utcnow(), 'canceled'
        task.status, task.lease_until = 'canceled', None
        cleanup = db.scalar(select(IndexTask).where(IndexTask.unit_id == unit.id,
            IndexTask.version == unit.current_version, IndexTask.operation == 'delete'))
        if cleanup is None:
            db.add(IndexTask(unit_id=unit.id, version=unit.current_version, operation='delete'))
        return True

    def terminal_index_failure(self, db, task):
        unit = db.get(KnowledgeUnit, task.unit_id)
        if unit.current_version == task.version:
            unit.index_status = 'failed'
        for job in db.scalars(select(ImportJob).where(ImportJob.unit_id == unit.id, ImportJob.status == 'running')):
            job.status, job.error = 'failed', task.error

    def process_index(self, claim):
        with self.heartbeat(IndexTask, claim):
            self._process_index(claim)

    def _process_index(self, claim):
        try:
            self.index_graph.invoke({'task_id': claim.id, 'generation': claim.generation})
        except Exception as exc:
            with self.factory.begin() as db:
                task = JobRepository(db, self.settings).owned(IndexTask, claim)
                if task is None:
                    return
                exhausted = task.attempts >= self.settings.worker_max_attempts
                task.status = 'failed' if exhausted else 'pending'
                task.error = safe_error(exc, '向量索引处理失败')
                task.lease_until = None if exhausted else utcnow()+timedelta(seconds=30*task.attempts)
                unit = db.get(KnowledgeUnit, task.unit_id)
                if unit.current_version == task.version:
                    unit.index_status = 'failed' if exhausted else 'pending'
                if exhausted:
                    self.terminal_index_failure(db, task)

    def load_chunks(self, state: IndexState):
        claim = Claim(state['task_id'], state['generation'])
        with self.factory.begin() as db:
            task = JobRepository(db, self.settings).owned(IndexTask, claim)
            if task is None:
                return {'proceed': False}
            unit = db.get(KnowledgeUnit, task.unit_id)
            if task.operation == 'upsert' and (unit.deleted_at or unit.current_version != task.version):
                task.status, task.lease_until = 'obsolete', None
                return {'proceed': False}
            if task.operation == 'upsert' and self.cancel_import_index(db, unit, task):
                return {'proceed': False}
            chunks = list(db.scalars(select(Chunk).where(Chunk.unit_id == unit.id,
                Chunk.version == task.version).order_by(Chunk.ordinal)))
            return {'proceed': True, 'unit_id': unit.id, 'version': task.version, 'operation': task.operation,
                'texts': [c.content for c in chunks], 'records': [dict(chunk_id=c.id, unit_id=unit.id,
                version=task.version, content_hash=c.content_hash, model_id=c.embedding_model) for c in chunks]}

    def embed_chunks(self, state: IndexState):
        log.info('Index %s: embed_chunks (%d chunks)', state['task_id'], len(state['texts']))
        vectors = self.infra.embedder.encode(state['texts'])
        require(len(state['records']) == len(vectors), '向量数量与切片不一致', 503)
        return {'vectors': vectors}

    def write_vectors(self, state: IndexState):
        claim = Claim(state['task_id'], state['generation'])
        with self.factory.begin() as db:
            task = JobRepository(db, self.settings).owned(IndexTask, claim)
            if task is None:
                return {'proceed': False}
            unit = db.get(KnowledgeUnit, task.unit_id)
            if task.operation == 'upsert' and self.cancel_import_index(db, unit, task):
                return {'proceed': False}
            if task.operation == 'upsert' and (unit.deleted_at or unit.current_version != task.version):
                task.status, task.lease_until = 'obsolete', None
                return {'proceed': False}
        self.infra.vectors.ensure()
        if state['operation'] == 'delete':
            self.infra.vectors.delete_unit(state['unit_id'])
        else:
            records = [dict(row, dense_vector=vector) for row, vector in zip(state['records'], state['vectors'])]
            self.infra.vectors.upsert(records)
            self.infra.vectors.delete_unit(state['unit_id'], before_version=state['version'])
        log.info('Index %s: write_vectors completed', claim.id)
        return {'proceed': True}

    def finish_index(self, state: IndexState):
        claim = Claim(state['task_id'], state['generation'])
        with self.factory.begin() as db:
            task = JobRepository(db, self.settings).owned(IndexTask, claim)
            if task is None:
                return {'proceed': False}
            unit = db.scalar(select(KnowledgeUnit).where(KnowledgeUnit.id == state['unit_id']).with_for_update())
            if task.operation == 'upsert' and self.cancel_import_index(db, unit, task):
                return {'proceed': False}
            if task.operation == 'upsert' and (unit.deleted_at or unit.current_version != task.version):
                task.status, task.lease_until = 'obsolete', None
                return {'proceed': False}
            task.status, task.lease_until, task.error = 'completed', None, ''
            unit.indexed_version = task.version if task.operation == 'upsert' else 0
            unit.index_status = 'ready' if task.operation == 'upsert' else 'deleted'
            for job in db.scalars(select(ImportJob).where(ImportJob.unit_id == unit.id, ImportJob.status == 'running')):
                job.status, job.phase, job.error = ('canceled' if job.cancel_requested else 'completed'), 5, ''
        return {'proceed': True}

    def run_once(self):
        with self.factory.begin() as db:
            for model in [ImportJob, IndexTask]:
                for task in JobRepository(db, self.settings).exhausted(model):
                    task.status, task.lease_until = 'failed', None
                    task.error = '后台处理租约过期且已达到重试上限，请手动重试'
                    if model is IndexTask:
                        self.terminal_index_failure(db, task)
        worked = False
        job_id = self.claim(ImportJob)
        if job_id:
            self.process_import(job_id)
            worked = True
        task_id = self.claim(IndexTask)
        if task_id:
            self.process_index(task_id)
            worked = True
        return worked

    def _heartbeat(self, stop):
        while True:
            self.infra.cache.touch_worker()
            if stop.wait(10):
                return

    def run(self, stop=None):
        from app.services.mining import MiningService
        stop = stop if stop is not None else Event()
        heartbeat = Thread(target=self._heartbeat, args=(stop,), daemon=True)
        heartbeat.start()
        try:
            while not stop.is_set():
                try:
                    worked = self.run_once()
                    if stop.is_set():
                        break
                    if time.monotonic()-self.last_mining >= self.settings.mining_interval_seconds:
                        with self.factory.begin() as db:
                            MiningService(db, self.settings, self.infra).run()
                        self.last_mining = time.monotonic()
                    if not worked:
                        stop.wait(self.settings.worker_poll_seconds)
                except KeyboardInterrupt:
                    return
                except Exception as exc:
                    log.error('Worker iteration failed (%s)', type(exc).__name__)
                    stop.wait(self.settings.worker_poll_seconds)
        finally:
            stop.set()
            heartbeat.join(timeout=1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    _, factory = build_database(settings.database_url)
    Worker(settings, factory, Infrastructure.from_settings(settings)).run()
