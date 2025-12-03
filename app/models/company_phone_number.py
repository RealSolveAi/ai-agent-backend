from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from app.persistance.db import Base
import enum


class NumberType(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    both = "both"


class CompanyPhoneNumber(Base):
    __tablename__ = "company_phone_numbers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    phone_number = Column(String(50), unique=True, nullable=False)
    friendly_name = Column(String(100), nullable=True)
    twilio_sid = Column(String(255), nullable=True)
    country_code = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    type = Column(Enum(NumberType), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="phone_numbers")
    call_logs = relationship("CallLog", back_populates="phone_number")
