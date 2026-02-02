from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Added role for authorization (admin/user)
    role = Column(String(20), default="user") 

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
