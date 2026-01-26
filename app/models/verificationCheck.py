from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.extension.extensions import db

class VerificationCheck(db.Model):
    __tablename__ = 'verification_checks'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), nullable=False, index=True)
    flag = Column(String(64), nullable=False)
    details = Column(JSONB, server_default='{}' )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
