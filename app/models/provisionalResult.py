# app/models/provisional_result.py
from sqlalchemy import Column, BigInteger, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.extension.extensions import db

class ProvisionalResult(db.Model):
    __tablename__ = 'provisional_results'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), nullable=False, index=True)
    proposed_rank = Column(Integer, nullable=False)
    submitted_by_vendor = Column(BigInteger, ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('event_id', 'team_id', name='uq_provisional_event_team'),
    )
