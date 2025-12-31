from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship, declared_attr
from app.persistance.db import Base
import enum


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"      # Programada
    reminded = "reminded"        # Recordatorio enviado
    in_progress = "in_progress"  # Llamada en curso
    completed = "completed"      # Completada
    cancelled = "cancelled"      # Cancelada
    missed = "missed"           # No se realizó


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    agent_profile_id = Column(Integer, ForeignKey("agent_profiles.id", ondelete="SET NULL"), nullable=True)
    call_log_id = Column(Integer, ForeignKey("call_logs.id", ondelete="SET NULL"), nullable=True)  # Vinculado cuando se realiza la llamada

    # Información de la cita
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scheduled_datetime = Column(DateTime(timezone=True), nullable=False)  # Guardado en UTC
    duration_minutes = Column(Integer, default=30)
    timezone = Column(String(50), nullable=True)  # Zona horaria para mostrar (ej: "America/Bogota")

    # Estado
    status = Column(Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.scheduled)
    notes = Column(Text, nullable=True)

    # Metadatos
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    @declared_attr
    def company(cls):
        return relationship("Company", back_populates="appointments")

    @declared_attr
    def contact(cls):
        return relationship("Contact", back_populates="appointments")

    @declared_attr
    def agent_profile(cls):
        return relationship("AgentProfile", back_populates="appointments")

    @declared_attr
    def call_log(cls):
        return relationship("CallLog", back_populates="appointment")

    @declared_attr
    def reminders(cls):
        return relationship("AppointmentReminder", back_populates="appointment", cascade="all, delete-orphan")
