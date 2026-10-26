from sqlalchemy import select
from app.models.entities import KnowledgeUnit, Attachment, UnitVersion
from .base import Repository


class KnowledgeRepository(Repository):
    def browse(self, condition, manage_acl, page, page_size, title='', category='', status=''):
        q = select(KnowledgeUnit).where(KnowledgeUnit.deleted_at.is_(None))
        if not manage_acl:
            q = q.where(condition)
        if title:
            q = q.where(condition, KnowledgeUnit.title.icontains(title, autoescape=True))
        if category:
            q = q.where(condition, KnowledgeUnit.category == category)
        if status:
            q = q.where(KnowledgeUnit.status == status)
        return self.page(q.order_by(KnowledgeUnit.updated_at.desc(), KnowledgeUnit.id), page, page_size)

    def attachments(self, unit_id):
        return list(self.db.scalars(select(Attachment).where(Attachment.unit_id == unit_id)))

    def versions(self, unit_id):
        return list(self.db.scalars(select(UnitVersion).where(UnitVersion.unit_id == unit_id)
                                   .order_by(UnitVersion.version.desc())))
