from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class UserData(Base):
    __tablename__ = "user_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(), unique=True, nullable=False)
    password = Column(String(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)