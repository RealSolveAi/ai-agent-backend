# app/services/save_call_to_db.py
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.persistance.db import SessionLocal
from app.models.call_log import CallLog, CallStatus, CallDirection
from app.models.call_turn import CallTurn, Speaker
from app.models.company_phone_number import CompanyPhoneNumber


def create_call_log(company_id: int, phone_number_id: int, call_sid: str, direction: str) -> int:
    db: Session = SessionLocal()
    try:
        call = CallLog(
            company_id=company_id,
            phone_number_id=phone_number_id,
            call_sid=call_sid,
            direction=direction,
            status=CallStatus.in_progress,
            start_time=datetime.now(timezone.utc)
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        return call.id
    finally:
        db.close()


def add_turn(call_log_id: int, speaker: Speaker, content: str, intent: str | None = None):
    db: Session = SessionLocal()
    try:
        turn = CallTurn(
            call_log_id=call_log_id,
            speaker=speaker,
            content=content,
            intent=intent
        )
        db.add(turn)
        db.commit()
    finally:
        db.close()


def finish_call(call_log_id: int, duration_seconds: int | None = None, summary: str | None = None):
    db: Session = SessionLocal()
    try:
        call = db.query(CallLog).filter(CallLog.id == call_log_id).first()
        if not call:
            return
        call.status = CallStatus.completed
        call.end_time = datetime.now(timezone.utc)
        if duration_seconds is not None:
            call.duration_seconds = duration_seconds
        if summary:
            call.transcription_summary = summary
        db.commit()
    finally:
        db.close()


def get_phone_number_by_number(phone_number: str) -> CompanyPhoneNumber | None:
    """Busca un CompanyPhoneNumber por su número de teléfono."""
    db: Session = SessionLocal()
    try:
        return db.query(CompanyPhoneNumber).filter(CompanyPhoneNumber.phone_number == phone_number).first()
    finally:
        db.close()


def get_phone_number_by_twilio_sid(twilio_sid: str) -> CompanyPhoneNumber | None:
    """Busca un CompanyPhoneNumber por su Twilio SID."""
    db: Session = SessionLocal()
    try:
        return db.query(CompanyPhoneNumber).filter(CompanyPhoneNumber.twilio_sid == twilio_sid).first()
    finally:
        db.close()


def create_call_log_from_phone_number(
    phone_number_str: str, 
    call_sid: str, 
    direction: str,
    from_number: str | None = None,
    contact_id: int | None = None,
    to_phone_number: str | None = None
) -> int | None:
    """
    Crea un CallLog buscando el CompanyPhoneNumber por número de teléfono.
    Para llamadas entrantes, busca por el número que recibe (TWILIO_PHONE_NUMBER).
    Para llamadas salientes, busca por el número desde el cual se llama (TWILIO_PHONE_NUMBER).
    
    Args:
        phone_number_str: Número de teléfono a buscar (normalmente TWILIO_PHONE_NUMBER)
        call_sid: SID de la llamada de Twilio
        direction: "inbound" o "outbound"
        from_number: Número desde el cual se llama (para llamadas salientes) o que llama (para entrantes)
    
    Returns:
        ID del CallLog creado o None si no se encuentra el número
    """
    db: Session = SessionLocal()
    try:
        phone_number = get_phone_number_by_number(phone_number_str)
        if not phone_number:
            print(f"⚠️ No se encontró CompanyPhoneNumber para el número: {phone_number_str}")
            return None
        
        call = CallLog(
            company_id=phone_number.company_id,
            phone_number_id=phone_number.id,
            contact_id=contact_id,
            call_sid=call_sid,
            direction=CallDirection.inbound if direction == "inbound" else CallDirection.outbound,
            status=CallStatus.in_progress,
            start_time=datetime.now(timezone.utc),
            to_phone_number=to_phone_number if direction == "outbound" else None,
            from_phone_number=from_number if direction == "inbound" else phone_number_str
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        print(f"✅ CallLog creado: ID={call.id}, CallSid={call_sid}, Company={phone_number.company_id}")
        return call.id
    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear CallLog: {e}")
        return None
    finally:
        db.close()
