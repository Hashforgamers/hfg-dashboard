from datetime import datetime
from app.extension.extensions import db


class VendorStaff(db.Model):
    __tablename__ = "vendor_staff"

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="staff")
    pin_code = db.Column(db.String(6), nullable=True)
    pin_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("vendor_id", "name", name="uq_vendor_staff_name"),
    )

    def to_dict(self, include_pin: bool = False):
        payload = {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "name": self.name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_pin:
            payload["pin_code"] = self.pin_code
        return payload
