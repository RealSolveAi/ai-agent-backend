# app/models/user.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from app.persistance.db import Base
import enum


class UserRole(str, enum.Enum):
    superadmin = "superadmin"  # Acceso total a todas las empresas
    admin = "admin"  # Administrador de su empresa
    agent = "agent"  # Agente de su empresa
    viewer = "viewer"  # Solo lectura de su empresa


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)  # NULL para superadmin
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.admin)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), nullable=True)
    last_logout = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="users")
