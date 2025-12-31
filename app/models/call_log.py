from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship, declared_attr
from app.persistance.db import Base
import enum


class CallDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class CallStatus(str, enum.Enum):
    initiated = "initiated"
    in_progress = "in_progress"
    completed = "completed"  # Llamada completada con interacción del usuario
    no_answer = "no_answer"  # No contestaron la llamada
    no_response = "no_response"  # Contestaron pero nunca hablaron/interactuaron
    failed = "failed"  # Falló por otras razones (busy, error, etc.)


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)

    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    phone_number_id = Column(Integer, ForeignKey("company_phone_numbers.id", ondelete="SET NULL"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)  # Contacto destino (para llamadas salientes)
    agent_profile_id = Column(Integer, ForeignKey("agent_profiles.id", ondelete="SET NULL"), nullable=True)  # AgentProfile usado en esta llamada

    call_sid = Column(String(255), unique=True, nullable=True)
    
    # Números de teléfono (para referencia rápida sin joins)
    to_phone_number = Column(String(50), nullable=True)  # Número destino (para llamadas salientes)
    from_phone_number = Column(String(50), nullable=True)  # Número origen (para llamadas entrantes)

    direction = Column(Enum(CallDirection), nullable=True)
    status = Column(Enum(CallStatus), nullable=True, default=CallStatus.initiated)

    duration_seconds = Column(Integer, nullable=True)
    transcription_summary = Column(Text, nullable=True)

    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)

    recording_url = Column(String, nullable=True)
    recording_sid = Column(String(255), nullable=True)  # SID de la grabación en Twilio
    recording_duration = Column(Integer, nullable=True)  # Duración de la grabación en segundos
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ✅ Relación con la empresa (la que faltaba)
    @declared_attr
    def company(cls):
        from app.models.company import Company
        return relationship("Company", back_populates="call_logs")

    # ✅ Relación con el número telefónico
    @declared_attr
    def phone_number(cls):
        from app.models.company_phone_number import CompanyPhoneNumber
        return relationship("CompanyPhoneNumber", back_populates="call_logs")

    # ✅ Relación con los turnos de conversación
    @declared_attr
    def turns(cls):
        from app.models.call_turn import CallTurn
        return relationship("CallTurn", back_populates="call", cascade="all, delete-orphan")
    
    # ✅ Relación con el contacto destino
    @declared_attr
    def contact(cls):
        return relationship("Contact", back_populates="call_logs")
    
    # ✅ Relación con cita (si la llamada fue programada)
    @declared_attr
    def appointment(cls):
        return relationship("Appointment", back_populates="call_log")
