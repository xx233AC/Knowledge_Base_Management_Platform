from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy import select, update, or_
from app.models.entities import ImportJob, IndexTask, utcnow


@dataclass(frozen=True)
class Claim:
    id: str
    generation: int


class JobRepository:
    """Lease generations fence state writes by workers whose claims have expired."""
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def claim(self, model):
        criteria = [model.status == 'running', model.unit_id.is_(None)] if model is ImportJob else [
            model.status.in_(['pending', 'running'])]
        task = self.db.scalar(select(model).where(*criteria, model.attempts < self.settings.worker_max_attempts,
            or_(model.lease_until.is_(None), model.lease_until < utcnow()))
            .order_by(model.created_at, model.id).with_for_update(skip_locked=True).limit(1))
        if task is None:
            return None
        task.attempts += 1
        task.lease_generation += 1
        task.lease_until = utcnow()+timedelta(seconds=self.settings.worker_lease_seconds)
        if model is IndexTask:
            task.status = 'running'
        return Claim(task.id, task.lease_generation)

    def owned(self, model, claim):
        return self.db.scalar(select(model).where(model.id == claim.id, model.lease_generation == claim.generation,
            model.status == 'running', model.lease_until > utcnow()).with_for_update())

    def renew(self, model, claim):
        return self.db.execute(update(model).where(model.id == claim.id, model.lease_generation == claim.generation,
            model.status == 'running', model.lease_until > utcnow())
            .values(lease_until=utcnow()+timedelta(seconds=self.settings.worker_lease_seconds))).rowcount == 1

    def exhausted(self, model):
        statuses = ['running'] if model is ImportJob else ['pending', 'running']
        return list(self.db.scalars(select(model).where(model.status.in_(statuses),
            model.attempts >= self.settings.worker_max_attempts, model.lease_until < utcnow())
            .with_for_update(skip_locked=True)))
