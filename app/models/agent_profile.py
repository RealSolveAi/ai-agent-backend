from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship, declared_attr
from sqlalchemy.dialects.postgresql import JSONB
from app.persistance.db import Base


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    
    # Información del agente
    name = Column(String(100), nullable=False)  # Nombre del agente (ej: "Lina", "Asistente Principal")
    voice = Column(String(50), default='coral')  # Voz de OpenAI: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar
    temperature = Column(Float, default=0.8)  # Temperatura del modelo (0.0 - 2.0)
    
    # Prompt personalizado
    prompt = Column(Text, nullable=True)  # Prompt del sistema personalizado para esta empresa
    
    # Configuración de horarios
    working_hours = Column(JSONB, nullable=True)  # Horarios de trabajo en formato JSON
    timezone = Column(String(50), nullable=True)  # Zona horaria del agente
    
    # Estado
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relación con la empresa
    @declared_attr
    def company(cls):
        # ✅ Usa solo el nombre en string para evitar circular import
        return relationship("Company", back_populates="agent_profiles")

