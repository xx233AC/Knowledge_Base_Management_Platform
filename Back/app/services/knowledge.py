from hashlib import sha256
from sqlalchemy import select
from app.core.errors import require
from app.models.entities import (KnowledgeUnit, UnitVersion, Chunk, IndexTask,
                                Faq, FaqSource, KnowledgeGap, utcnow, new_id)
from app.common.text import split_text
from app.repositories.knowledge import KnowledgeRepository
from .access import AccessService
from .identity import iso


class KnowledgeService:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings
        self.repo, self.access = KnowledgeRepository(db), AccessService(db)

    def active(self, entity_id, lock=False):
        unit = self.repo.get(KnowledgeUnit, entity_id, lock=lock)
        require(unit.deleted_at is None, '知识单元不存在', 404)
        return unit

    def serialize(self, actor, unit, detail=True):
        allowed = self.access.allowed(actor, unit.id)
        base = dict(id=unit.id, code=unit.unit_code, title='未授权知识单元', content='', summary='',
                    category='', tags=[], fileType=unit.file_type, attachments=[], status=unit.status,
                    creatorId=unit.creator_id, updatedAt=iso(unit.updated_at), acl=[], versions=[],
                    restricted=not allowed, indexStatus=unit.index_status)
        if 'knowledge.permissions' in actor.permissions:
            base['acl'] = self.access.grants(unit.id)
        if not allowed:
            return base
        base.update(title=unit.title, content=unit.content if detail else '', summary=unit.summary,
                    category=unit.category, tags=unit.tags, acl=self.access.grants(unit.id))
        base['attachments'] = [dict(id=a.id, name=a.file_name, size=a.size)
                               for a in self.repo.attachments(unit.id)]
        if detail:
            base['versions'] = [dict(version=v.version, date=iso(v.created_at), editor=v.editor_id,
                                     title=v.title, content=v.content)
                for v in self.repo.versions(unit.id)]
        return base

    def list(self, actor, page, page_size, title='', category='', status=''):
        actor.need('knowledge.read')
        rows, total = self.repo.browse(self.access.condition(actor), 'knowledge.permissions' in actor.permissions,
                                      page, page_size, title, category, status)
        return dict(items=[self.serialize(actor, r, detail=False) for r in rows], total=total)

    def get(self, actor, entity_id):
        actor.need('knowledge.read')
        unit = self.active(entity_id)
        self.access.need(actor, entity_id)
        return self.serialize(actor, unit)

    def rebuild_chunks(self, unit, actor_id):
        self.db.add(UnitVersion(unit_id=unit.id, version=unit.current_version, title=unit.title,
                               content=unit.content, editor_id=actor_id))
        pieces = split_text(unit.content, self.settings.chunk_size, self.settings.chunk_overlap)
        for i, p in enumerate(pieces):
            self.db.add(Chunk(unit_id=unit.id, version=unit.current_version, ordinal=i, content=p.content,
                heading=p.heading, page=p.page, start_offset=p.start_offset, end_offset=p.end_offset,
                content_hash=sha256(p.content.encode()).hexdigest()))
        unit.index_status = 'pending'
        self.db.add(IndexTask(unit_id=unit.id, version=unit.current_version))

    def invalidate_sources(self, unit):
        faq_ids = list(self.db.scalars(select(FaqSource.faq_id).where(FaqSource.unit_id == unit.id)))
        for faq in self.db.scalars(select(Faq).where(Faq.id.in_(faq_ids))):
            faq.cache_enabled = False
            faq.status = 'pending_review'
            faq.revision += 1

    def save(self, actor, data, entity_id=None):
        actor.need('knowledge.update' if entity_id else 'knowledge.create')
        creating = entity_id is None
        if creating:
            require(data.get('title', '').strip() and data.get('content', '').strip(), '标题与正文不能为空')
            unit = KnowledgeUnit(unit_code='KB-'+new_id().replace('-', '')[:16].upper(),
                                 title=data['title'].strip(), content=data['content'], creator_id=actor.user.id)
            self.db.add(unit)
            self.db.flush()
        else:
            unit = self.active(entity_id, lock=True)
            self.access.need(actor, entity_id)
        if data.get('acl') is not None:
            actor.need('knowledge.permissions')
            self.access.validate_grants(data['acl'])
        changed = creating or any(data.get(f) is not None and data[f] != getattr(unit, f)
                                   for f in ['title', 'content'])
        if not creating and changed:
            unit.current_version += 1
        old_status = unit.status
        for field in ['title', 'content', 'summary', 'category', 'tags', 'status']:
            if data.get(field) is not None:
                if field in ['title', 'content', 'category']:
                    require(bool(data[field].strip()), '标题、正文和分类不能为空')
                setattr(unit, field, data[field])
        if data.get('summary') is None and changed:
            unit.summary = unit.content[:300]
        if changed:
            self.rebuild_chunks(unit, actor.user.id)
        if changed or old_status != unit.status:
            self.invalidate_sources(unit)
        if data.get('acl') is not None:
            self.access.replace(unit, data['acl'])
        if data.get('attachments') is not None:
            existing = self.repo.attachments(unit.id)
            # Existing UI sends name/size; it may detach but never attach an arbitrary MinIO key.
            retained = {(a.get('name'), a.get('size')) for a in data['attachments']}
            require(retained <= {(a.file_name, a.size) for a in existing}, '附件须先通过导入接口上传')
            for a in existing:
                if (a.file_name, a.size) not in retained:
                    a.unit_id = None
        if data.get('gap_id'):
            actor.need('gaps.manage')
            gap = self.repo.get(KnowledgeGap, data['gap_id'], lock=True)
            gap.status, gap.resolved_unit_id = 'resolved', unit.id
        self.db.flush()
        self.repo.audit(actor.user.id, 'knowledge.save', unit.id, version=unit.current_version)
        return self.serialize(actor, unit)

    def set_permissions(self, actor, entity_id, grants):
        actor.need('knowledge.permissions')
        unit = self.active(entity_id, lock=True)
        self.access.replace(unit, grants)
        self.repo.audit(actor.user.id, 'knowledge.permissions', unit.id, grants=len(grants))
        return self.serialize(actor, unit)

    def reindex(self, actor, entity_id):
        actor.need('knowledge.update')
        unit = self.active(entity_id, lock=True)
        self.access.need(actor, entity_id)
        self.queue_reindex(unit)
        self.repo.audit(actor.user.id, 'knowledge.reindex', unit.id)
        return self.serialize(actor, unit)

    def queue_reindex(self, unit):
        task = self.db.scalar(select(IndexTask).where(IndexTask.unit_id == unit.id,
            IndexTask.version == unit.current_version, IndexTask.operation == 'upsert').with_for_update())
        if task is None:
            self.db.add(IndexTask(unit_id=unit.id, version=unit.current_version))
        else:
            from .identity import iso
            require(task.status != 'running' or task.lease_until is None or iso(task.lease_until) <= iso(utcnow()),
                    '索引正在处理中，请稍后重试', 409)
            task.status, task.attempts, task.lease_until, task.error = 'pending', 0, None, ''
        unit.index_status = 'pending'
        self.db.flush()

    def remove(self, actor, ids):
        actor.need('knowledge.delete')
        units = self.repo.all_ids(KnowledgeUnit, ids)
        for u in units:
            self.access.need(actor, u.id)
            require(u.deleted_at is None, '知识已删除', 404)
        for u in units:
            self.invalidate_sources(u)
            u.deleted_at = utcnow()
            u.index_status = 'deleting'
            self.db.add(IndexTask(unit_id=u.id, version=u.current_version, operation='delete'))
            for gap in self.db.scalars(select(KnowledgeGap).where(KnowledgeGap.resolved_unit_id == u.id)):
                gap.resolved_unit_id, gap.status = None, 'unresolved'
            self.repo.audit(actor.user.id, 'knowledge.delete', u.id)
