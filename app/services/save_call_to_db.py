# app/services/save_call_to_db.py
from sqlalchemy.orm import Session, joinedload
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


def finish_call(call_log_id: int, duration_seconds: int | None = None, summary: str | None = None, recording_url: str | None = None):
    """
    Finaliza una llamada (actualiza end_time y summary).
    NO marca como completed hasta que tengamos recording_duration.
    La duración se obtiene de recording_duration si está disponible, 
    de lo contrario se usa duration_seconds si se proporciona.
    Determina el estado correcto basándose en si hubo interacción del usuario.
    """
    db: Session = SessionLocal()
    try:
        # Cargar la llamada con sus turnos para poder determinar el estado
        call = db.query(CallLog).options(
            joinedload(CallLog.turns)
        ).filter(CallLog.id == call_log_id).first()
        
        if not call:
            return
        
        end_time = datetime.now(timezone.utc)
        call.end_time = end_time
        
        # Usar recording_duration si está disponible, de lo contrario usar duration_seconds si se proporciona
        if call.recording_duration is not None:
            call.duration_seconds = call.recording_duration
            # Determinar el estado correcto basándose en la interacción del usuario
            call.status = determine_call_status(call)
        elif duration_seconds is not None:
            call.duration_seconds = duration_seconds
        
        if summary:
            call.transcription_summary = summary
        
        if recording_url:
            call.recording_url = recording_url
        
        db.commit()
        print(f"✅ Llamada finalizada: ID={call_log_id}, Duración={call.duration_seconds}s, Status={call.status.value if call.status else 'N/A'}, Recording URL: {recording_url or 'N/A'}")
    except Exception as e:
        db.rollback()
        print(f"❌ Error al finalizar llamada: {e}")
    finally:
        db.close()


def is_voicemail_message(content: str) -> bool:
    """
    Detecta si un mensaje es del buzón de voz (voicemail) de Twilio.
    Los mensajes del buzón de voz son automáticos y no indican que el usuario contestó.
    """
    if not content:
        return False
    
    content_lower = content.lower().strip()
    
    # Frases comunes del buzón de voz en español
    voicemail_phrases = [
        "oír el tono",
        "grabe su mensaje",
        "para finalizar",
        "presione numeral",
        "mensaje de voz guardado",
        "mensaje guardado",
        "deje su mensaje",
        "después del tono",
        "after the tone",
        "leave a message",
        "press pound",
        "voicemail",
        "buzón de voz",
        "mailbox",
        "greeting",
        "unavailable",
        "not available"
    ]
    
    # Verificar si el contenido contiene alguna frase del buzón de voz
    for phrase in voicemail_phrases:
        if phrase in content_lower:
            return True
    
    # También detectar mensajes muy cortos que son típicos del buzón de voz
    # (solo si son muy específicos)
    if len(content_lower) < 10 and any(word in content_lower for word in ["tono", "tone", "mensaje", "message"]):
        return True
    
    return False


def determine_call_status(call: CallLog) -> CallStatus:
    """
    Determina el estado correcto de una llamada basándose en:
    - Si hay turnos del usuario REAL (no buzón de voz) → completed
    - Si solo hay turnos del buzón de voz → no_answer (no contestó)
    - Si no hay turnos del usuario pero hay recording_duration → no_response
    - Si el estado actual es no_answer → no_answer (mantener)
    - Si el estado actual es failed → failed (mantener)
    """
    # Si ya está marcado como no_answer o failed, mantenerlo
    if call.status == CallStatus.no_answer or call.status == CallStatus.failed:
        return call.status
    
    # Si tenemos recording_duration, verificar si hubo interacción del usuario REAL
    if call.recording_duration is not None:
        # Filtrar turnos del usuario que NO sean del buzón de voz
        real_user_turns = [
            turn for turn in call.turns 
            if turn.speaker == Speaker.user and not is_voicemail_message(turn.content)
        ]
        
        if len(real_user_turns) > 0:
            # Hubo interacción real del usuario → completed
            return CallStatus.completed
        else:
            # Verificar si hay turnos del usuario que sean del buzón de voz
            voicemail_turns = [
                turn for turn in call.turns 
                if turn.speaker == Speaker.user and is_voicemail_message(turn.content)
            ]
            
            if len(voicemail_turns) > 0:
                # Solo hay mensajes del buzón de voz → no_answer (no contestó)
                return CallStatus.no_answer
            else:
                # No hubo interacción del usuario → no_response
                return CallStatus.no_response
    
    # Si aún no tenemos recording_duration, mantener el estado actual
    return call.status if call.status else CallStatus.in_progress


def update_call_recording_url(call_sid: str, recording_url: str, recording_sid: str | None = None, recording_duration: int | None = None):
    """
    Actualiza el recording_url, recording_sid y recording_duration de una llamada por su call_sid.
    También actualiza duration_seconds con recording_duration si está disponible.
    Determina el estado correcto basándose en si hubo interacción del usuario.
    """
    db: Session = SessionLocal()
    try:
        # Cargar la llamada con sus turnos para poder determinar el estado
        call = db.query(CallLog).options(
            joinedload(CallLog.turns)
        ).filter(CallLog.call_sid == call_sid).first()
        
        if not call:
            print(f"⚠️ No se encontró CallLog para CallSid: {call_sid}")
            return False
        
        call.recording_url = recording_url
        if recording_sid:
            call.recording_sid = recording_sid
        if recording_duration is not None:
            call.recording_duration = recording_duration
            # Usar recording_duration como duration_seconds
            call.duration_seconds = recording_duration
            
            # Determinar el estado correcto basándose en la interacción del usuario
            call.status = determine_call_status(call)
            
            # Si no tenemos end_time, establecerlo ahora
            if not call.end_time:
                call.end_time = datetime.now(timezone.utc)
        
        db.commit()
        print(f"✅ Recording URL actualizado para CallSid: {call_sid}, URL: {recording_url}, SID: {recording_sid}, Duration: {recording_duration}s, Status: {call.status.value if call.status else 'N/A'}")
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ Error al actualizar recording URL: {e}")
        import traceback
        traceback.print_exc()
        return False
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
