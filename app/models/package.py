# models/package.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, CheckConstraint
from sqlalchemy.sql import func
from app.extension.extensions import db

class Package(db.Model):
    __tablename__ = 'packages'
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)          # 'base','pro','custom'
    name = Column(String(64), nullable=False)
    pc_limit = Column(Integer, nullable=False)
    is_custom = Column(Boolean, nullable=False, default=False)
    features = Column(JSON, nullable=False, default={})             # e.g., {"ws_priority": "standard"}
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint('pc_limit >= 0', name='ck_packages_pc_limit_nonneg'),
    )
