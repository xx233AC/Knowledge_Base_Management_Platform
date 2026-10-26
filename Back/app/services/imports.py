from pathlib import PurePosixPath
from hashlib import sha256
from datetime import timezone
import io
import zipfile
from sqlalchemy import select
from app.common.text import safe_upload_path
from app.core.errors import BusinessError, require
from app.models.entities import Attachment, ImportJob, KnowledgeUnit, new_id, utcnow
from app.repositories.base import Repository
from .identity import iso

ALLOWED = {'pdf', 'md', 'markdown', 'doc', 'docx', 'txt'}


class ImportService:
    def __init__(self, db, settings, infrastructure):
        self.db, self.settings, self.infra = db, settings, infrastructure
        self.repo = Repository(db)

    def serialize(self, job):
        a = self.repo.get(Attachment, job.attachment_id)
        return dict(id=job.id, name=a.file_name, path=job.relative_path, size=a.size,
                    phase=job.phase, status=job.status, startedAt=iso(job.created_at),
                    unitId=job.unit_id, error=job.error)

    def _waited(self, created_at):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return (utcnow()-created_at).total_seconds()

    def _expire_waiting(self, job, worker_alive):
        """Fail jobs no worker ever claimed. A live worker may merely be busy, so never expire then."""
        if job.status != 'running' or job.lease_until is not None or job.attempts or job.phase:
            return
        waited = self._waited(job.created_at)
        if waited < self.settings.import_wait_timeout_seconds or worker_alive is not False:
            return
        job.status = 'failed'
        job.error = '等待处理进程超时：%d 秒内没有 Worker 领取任务，请检查后端自动处理进程日志或重启后端后重试' % waited

    def upload(self, actor, files, paths):
        actor.need('knowledge.import')
        require(0 < len(files) <= self.settings.upload_max_files, '上传文件数量超限')
        require(not paths or len(paths) == len(files), '文件与相对路径数量不一致')
        prepared = []
        for i, f in enumerate(files):
            path = safe_upload_path(paths[i] if paths else '', f.filename or '')
            name = PurePosixPath(path).name
            require(name and len(name) <= 255, '文件名不合法')
            ext = PurePosixPath(name).suffix[1:].lower()
            require(ext in ALLOWED, '仅支持 PDF、Markdown、Word 和 TXT')
            data = f.file.read(self.settings.upload_max_bytes+1)
            require(0 < len(data) <= self.settings.upload_max_bytes, '文件为空或超过 50 MB 限制', 413)
            if ext == 'pdf':
                require(data.lstrip().startswith(b'%PDF-'), '文件内容与 PDF 扩展名不符')
            if ext == 'docx':
                require(zipfile.is_zipfile(io.BytesIO(data)), 'Word 文件格式无效')
            prepared.append((path, name, data, f.content_type or 'application/octet-stream'))
        jobs = []
        for path, name, data, mime in prepared:
            object_key = 'originals/'+new_id()+'/'+name
            try:
                self.infra.storage.put(object_key, data, mime)
            except BusinessError:
                raise
            except Exception as exc:
                raise BusinessError(503, '原文件存储失败，请检查 MinIO 配置和存储桶') from exc
            a = Attachment(uploader_id=actor.user.id, file_name=name, object_key=object_key,
                           bucket=self.settings.minio_bucket, mime_type=mime, size=len(data), sha256=sha256(data).hexdigest())
            self.db.add(a)
            self.db.flush()
            job = ImportJob(owner_id=actor.user.id, attachment_id=a.id, relative_path=path)
            self.db.add(job)
            self.db.flush()
            jobs.append(self.serialize(job))
        self.repo.audit(actor.user.id, 'knowledge.import', count=len(jobs))
        return dict(jobs=jobs)

    def get(self, actor, job_id):
        actor.need('knowledge.import')
        job = self.repo.get(ImportJob, job_id)
        require(job.owner_id == actor.user.id or 'knowledge.permissions' in actor.permissions,
                '你没有查看此任务的权限', 403)
        self._expire_waiting(job, self.infra.cache.worker_alive())
        return self.serialize(job)

    def cancel(self, actor, job_id):
        self.get(actor, job_id)
        job = self.repo.get(ImportJob, job_id, lock=True)
        if job.status == 'running':
            job.cancel_requested = True
            # A queued job can be canceled immediately; a claimed job stops at its next checkpoint.
            if not job.lease_until:
                job.status = 'canceled'

    def retry(self, actor, job_id):
        self.get(actor, job_id)
        job = self.repo.get(ImportJob, job_id, lock=True)
        require(job.status == 'failed', '只有失败任务可以重试', 409)
        if job.unit_id:
            from .knowledge import KnowledgeService
            unit = self.repo.get(KnowledgeUnit, job.unit_id, lock=True)
            require(unit.deleted_at is None, '知识已删除，请重新导入', 409)
            KnowledgeService(self.db, self.settings).queue_reindex(unit)
            job.phase = 3
        else:
            job.phase = 0
        job.status, job.attempts, job.lease_until, job.error = 'running', 0, None, ''
        job.cancel_requested = False
        self.db.flush()
        self.repo.audit(actor.user.id, 'knowledge.import_retry', job.id)
        return self.serialize(job)

    def list(self, actor, page, page_size):
        actor.need('knowledge.import')
        q = select(ImportJob)
        if 'knowledge.permissions' not in actor.permissions:
            q = q.where(ImportJob.owner_id == actor.user.id)
        jobs, total = self.repo.page(q.order_by(ImportJob.created_at.desc(), ImportJob.id), page, page_size)
        alive = self.infra.cache.worker_alive() if jobs else None
        for job in jobs:
            self._expire_waiting(job, alive)
        return dict(items=[self.serialize(j) for j in jobs], total=total)
