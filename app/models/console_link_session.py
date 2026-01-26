# app/models/console_link_session.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class ConsoleLinkStatus:
    ACTIVE = 'active'
    CLOSED = 'closed'
    STALE = 'stale'

class ConsoleLinkSession(db.Model):
    __tablename__ = 'console_link_sessions'
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False, index=True)
    console_id = Column(Integer, ForeignKey('consoles.id', ondelete='CASCADE'), nullable=False, index=True)
    kiosk_id = Column(String(64), nullable=True)

    session_token = Column(String(128), unique=True, nullable=False, index=True)
    status = Column(String(16), nullable=False, default=ConsoleLinkStatus.ACTIVE, index=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    close_reason = Column(String(64), nullable=True)

    vendor = relationship('Vendor')
    console = relationship('Console')

# Fast lookups
Index('ix_cls_vendor_active', ConsoleLinkSession.vendor_id, ConsoleLinkSession.status)
Index('ix_cls_console_active', ConsoleLinkSession.console_id, ConsoleLinkSession.status)
