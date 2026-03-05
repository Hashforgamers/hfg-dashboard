from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extension.extensions import db


class ControllerPricingRule(db.Model):
    __tablename__ = "controller_pricing_rules"

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    available_game_id = Column(
        Integer,
        ForeignKey("available_games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_price = Column(Numeric(10, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship("Vendor", backref="controller_pricing_rules")
    available_game = relationship("AvailableGame", backref="controller_pricing_rules")
    tiers = relationship(
        "ControllerPricingTier",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="ControllerPricingTier.quantity.asc()",
    )

    __table_args__ = (
        UniqueConstraint("vendor_id", "available_game_id", name="uq_controller_rule_vendor_game"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "available_game_id": self.available_game_id,
            "console_type": self.available_game.game_name.lower() if self.available_game else None,
            "base_price": float(self.base_price),
            "is_active": self.is_active,
            "tiers": [tier.to_dict() for tier in self.tiers if tier.is_active],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
