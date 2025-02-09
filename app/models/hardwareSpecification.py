from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class HardwareSpecification(db.Model):
    __tablename__ = 'hardware_specifications'
    
    id = Column(Integer, primary_key=True)
    processor_type = Column(String(100), nullable=False)
    graphics_card = Column(String(100), nullable=False)
    ram_size = Column(String(50), nullable=False)
    storage_capacity = Column(String(50), nullable=False)
    connectivity = Column(String(200), nullable=True)
    
    # Foreign key and relationship to Console
    console_id = Column(Integer, ForeignKey('consoles.id'), nullable=False)
    console = relationship('Console', back_populates='hardware_specifications')

    def __repr__(self):
        return f"<HardwareSpecification processor_type={self.processor_type} graphics_card={self.graphics_card}>"
