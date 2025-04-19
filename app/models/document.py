from app.extension.extensions import db

from datetime import datetime

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    document_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)  # Can store Google Drive URL or File ID
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(db.String(20), default='unverified')  # New field for verification status
    
    # In document.py
    vendor = db.relationship("Vendor", back_populates="documents")
