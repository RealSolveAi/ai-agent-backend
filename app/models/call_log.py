from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.persistance.db import Base

class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    call_sid = Column(String(100), unique=True)
    duration = Column(Float)  # duración en segundos
    transcript = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relación inversa
    user = relationship("User", back_populates="calls")
