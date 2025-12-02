from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship, declared_attr
from app.persistance.db import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=True)
    status = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)  # Para desactivar empresa y todos sus usuarios
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def users(cls):
        from app.models.user import User
        return relationship("User", back_populates="company", cascade="all, delete-orphan")

    @declared_attr
    def phone_numbers(cls):
        from app.models.company_phone_number import CompanyPhoneNumber
        return relationship("CompanyPhoneNumber", back_populates="company", cascade="all, delete-orphan")

    # ✅ Usa solo el nombre en string para evitar circular import
    @declared_attr
    def call_logs(cls):
        return relationship("CallLog", back_populates="company", cascade="all, delete-orphan")
    
    # ✅ Relación con contactos
    @declared_attr
    def contacts(cls):
        return relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    
    # ✅ Relación con agent_profiles
    @declared_attr
    def agent_profiles(cls):
        # ✅ Usa solo el nombre en string para evitar circular import
        return relationship("AgentProfile", back_populates="company", cascade="all, delete-orphan")