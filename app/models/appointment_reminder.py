from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship, declared_attr
from app.persistance.db import Base
import enum


class ReminderType(str, enum.Enum):
    notification = "notification"  # Solo notificación interna (registro en DB)
    call = "call"                 # Llamada automática al contacto
    both = "both"                 # Ambos: notificación + llamada


class ReminderStatus(str, enum.Enum):
    pending = "pending"       # Pendiente de ejecutar
    sent = "sent"            # Ejecutado exitosamente
    failed = "failed"        # Falló al ejecutar
    cancelled = "cancelled"  # Cancelado (por cancelación de cita o actualización)


class AppointmentReminder(Base):
    __tablename__ = "appointment_reminders"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False)

    # Configuración del recordatorio
    reminder_type = Column(Enum(ReminderType), nullable=False, default=ReminderType.notification)
    time_before_minutes = Column(Integer, nullable=False)  # Minutos antes de la cita (ej: 60 = 1 hora, 1440 = 1 día)
    reminder_datetime = Column(DateTime(timezone=True), nullable=False)  # Fecha/hora calculada para ejecutar el recordatorio (UTC)

    # Estado
    status = Column(Enum(ReminderStatus), nullable=False, default=ReminderStatus.pending)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadatos
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relación con la cita
    @declared_attr
    def appointment(cls):
        return relationship("Appointment", back_populates="reminders")
