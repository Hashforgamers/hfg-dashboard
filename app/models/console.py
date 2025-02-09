from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from .availableGame import available_game_console 

class Console(db.Model):
    __tablename__ = 'consoles'
    
    id = Column(Integer, primary_key=True)
    console_number = Column(Integer, nullable=False)
    model_number = Column(String(50), nullable=False)
    serial_number = Column(String(100), nullable=False)
    brand = Column(String(50), nullable=False)
    console_type = Column(String(50), nullable=False)
    release_date = Column(Date, nullable=False)
    description = Column(String(500), nullable=True)

    # Relationships
    hardware_specifications = relationship('HardwareSpecification', back_populates='console', uselist=False, cascade="all, delete-orphan")
    maintenance_status = relationship('MaintenanceStatus', back_populates='console', uselist=False, cascade="all, delete-orphan")
    price_and_cost = relationship('PriceAndCost', back_populates='console', uselist=False, cascade="all, delete-orphan")
    additional_details = relationship('AdditionalDetails', back_populates='console', uselist=False, cascade="all, delete-orphan")


    # Many-to-Many Relationship with AvailableGame
    available_games = relationship('AvailableGame', secondary=available_game_console, back_populates='consoles')

    def __repr__(self):
        return f"<Console console_type={self.console_type} model_number={self.model_number}>"
