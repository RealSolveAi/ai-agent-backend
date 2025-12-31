# app/models/contact.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Time, Boolean
from sqlalchemy.orm import relationship, declared_attr
from app.persistance.db import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    
    # Información básica
    name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=False)
    email = Column(String(255), nullable=True)
    
    # Información para el agente de IA
    description = Column(Text, nullable=True)  # Contexto sobre el contacto para el agente
    notes = Column(Text, nullable=True)  # Notas adicionales
    
    # Configuración de llamadas
    preferred_call_time_start = Column(Time, nullable=True)  # Hora preferida inicio
    preferred_call_time_end = Column(Time, nullable=True)  # Hora preferida fin
    timezone = Column(String(50), nullable=True)  # Zona horaria del contacto
    
    # Metadatos
    tags = Column(String(500), nullable=True)  # Tags separados por comas (ej: "cliente,prioritario,recordar_cita")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relación con la empresa
    @declared_attr
    def company(cls):
        from app.models.company import Company
        return relationship("Company", back_populates="contacts")
    
    # Relación con llamadas
    @declared_attr
    def call_logs(cls):
        from app.models.call_log import CallLog
        return relationship("CallLog", back_populates="contact")
    
    # Relación con citas
    @declared_attr
    def appointments(cls):
        return relationship("Appointment", back_populates="contact")

