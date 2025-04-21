from sqlalchemy import Column, Integer, String, Date, Sequence
from sqlalchemy.orm import relationship, foreign
from app.extension.extensions import db
from sqlalchemy.sql import and_

class User(db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, Sequence('user_id_seq', start=2000), primary_key=True)
    fid = Column(String(255), unique=True, nullable=False)
    avatar_path = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    gender = Column(String(50), nullable=True)
    dob = Column(Date, nullable=True)
    game_username = Column(String(255), unique=True, nullable=False)

    contact_info = relationship(
        "ContactInfo",  # ← STRING REFERENCE
        primaryjoin="and_(foreign(ContactInfo.parent_id) == User.id, ContactInfo.parent_type == 'user')",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
