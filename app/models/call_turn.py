# app/models/call_turn.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, ForeignKey, String, DateTime, Enum
from sqlalchemy.orm import relationship
from app.persistance.db import Base
import enum


class Speaker(str, enum.Enum):
    user = "user"          # el que llamó / cliente
    assistant = "assistant"  # Lina
    system = "system"      # mensajes internos, errores, etc.


class CallTurn(Base):
    __tablename__ = "call_turns"

    id = Column(Integer, primary_key=True, index=True)
    call_log_id = Column(Integer, ForeignKey("call_logs.id", ondelete="CASCADE"), nullable=False)

    # quién habló en este turno (user / assistant / system)
    speaker = Column(Enum(Speaker), nullable=False, default=Speaker.user)

    # texto completo que tenemos
    content = Column(Text, nullable=False)

    # opcional: la intención que detectamos (agenda_cita, info_empresa, interesado, etc.)
    intent = Column(String(100), nullable=True)

    # opcional: confianza del modelo que clasificó
    confidence = Column(Integer, nullable=True)  # 0-100 (simple)

    # marca de tiempo real
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relación inversa
    call = relationship("CallLog", back_populates="turns")
