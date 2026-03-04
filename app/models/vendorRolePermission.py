from app.extension.extensions import db


class VendorRolePermission(db.Model):
    __tablename__ = "vendor_role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(32), nullable=False)
    permission = db.Column(db.String(64), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("vendor_id", "role", "permission", name="uq_vendor_role_permission"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "role": self.role,
            "permission": self.permission,
        }
