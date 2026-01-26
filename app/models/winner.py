from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.extension.extensions import db

class Winner(db.Model):
    __tablename__ = 'winners'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    verified_snapshot = Column(JSONB)
    published_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('event_id', 'rank', name='uq_winner_event_rank'),
        db.UniqueConstraint('event_id', 'team_id', name='uq_winner_event_team'),
    )
