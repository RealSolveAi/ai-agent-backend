# app/services/call_service.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from app.persistance.db import SessionLocal
from app.models.call_log import CallLog
from app.models.call_turn import CallTurn
from typing import Optional
from datetime import datetime


def get_calls_by_company(
    company_id: int,
    limit: int = 50,
    offset: int = 0,
    phone_number_id: Optional[int] = None,
    status: Optional[str] = None
):
    """
    Obtiene las llamadas de una empresa con información básica.
    """
    db = SessionLocal()
    try:
        query = db.query(CallLog).filter(CallLog.company_id == company_id)
        
        if phone_number_id:
            query = query.filter(CallLog.phone_number_id == phone_number_id)
        
        if status:
            query = query.filter(CallLog.status == status)
        
        # Cargar relaciones para evitar N+1 queries
        calls = query.options(
            joinedload(CallLog.phone_number),
            joinedload(CallLog.turns)
        ).order_by(desc(CallLog.start_time)).offset(offset).limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "calls": [
                {
                    "id": call.id,
                    "call_sid": call.call_sid,
                    "direction": call.direction.value if call.direction else None,
                    "status": call.status.value if call.status else None,
                    "duration_seconds": call.duration_seconds,
                    "start_time": call.start_time.isoformat() if call.start_time else None,
                    "end_time": call.end_time.isoformat() if call.end_time else None,
                    "phone_number": {
                        "id": call.phone_number.id if call.phone_number else None,
                        "phone_number": call.phone_number.phone_number if call.phone_number else None,
                        "friendly_name": call.phone_number.friendly_name if call.phone_number else None,
                    } if call.phone_number else None,
                    "turns_count": len(call.turns) if call.turns else 0,
                    "transcription_summary": call.transcription_summary,
                    "recording_url": call.recording_url,
                }
                for call in calls
            ]
        }
    except Exception as e:
        return {"error": f"Error al obtener llamadas: {str(e)}"}
    finally:
        db.close()


def get_call_detail(call_id: int):
    """
    Obtiene el detalle completo de una llamada con su timeline de conversación.
    """
    db = SessionLocal()
    try:
        # Cargar relaciones para evitar N+1 queries
        call = db.query(CallLog).options(
            joinedload(CallLog.phone_number),
            joinedload(CallLog.company),
            joinedload(CallLog.turns)
        ).filter(CallLog.id == call_id).first()
        
        if not call:
            return {"error": "Llamada no encontrada"}
        
        # Los turnos ya están cargados en call.turns, solo necesitamos ordenarlos
        turns = sorted(call.turns, key=lambda t: t.created_at if t.created_at else datetime.min)
        
        return {
            "id": call.id,
            "call_sid": call.call_sid,
            "direction": call.direction.value if call.direction else None,
            "status": call.status.value if call.status else None,
            "duration_seconds": call.duration_seconds,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "end_time": call.end_time.isoformat() if call.end_time else None,
            "transcription_summary": call.transcription_summary,
            "recording_url": call.recording_url,
            "company": {
                "id": call.company.id if call.company else None,
                "name": call.company.name if call.company else None,
            } if call.company else None,
            "phone_number": {
                "id": call.phone_number.id if call.phone_number else None,
                "phone_number": call.phone_number.phone_number if call.phone_number else None,
                "friendly_name": call.phone_number.friendly_name if call.phone_number else None,
            } if call.phone_number else None,
            "timeline": [
                {
                    "id": turn.id,
                    "speaker": turn.speaker.value if turn.speaker else None,
                    "content": turn.content,
                    "intent": turn.intent,
                    "confidence": turn.confidence,
                    "timestamp": turn.created_at.isoformat() if turn.created_at else None,
                }
                for turn in turns
            ],
            "turns_count": len(turns)
        }
    except Exception as e:
        return {"error": f"Error al obtener detalle de llamada: {str(e)}"}
    finally:
        db.close()


def get_calls_by_phone_number(
    phone_number_id: int,
    limit: int = 50,
    offset: int = 0
):
    """
    Obtiene las llamadas de un número telefónico específico por ID.
    """
    db = SessionLocal()
    try:
        # Cargar relaciones para evitar N+1 queries
        calls = db.query(CallLog).options(
            joinedload(CallLog.turns)
        ).filter(
            CallLog.phone_number_id == phone_number_id
        ).order_by(desc(CallLog.start_time)).offset(offset).limit(limit).all()
        
        total = db.query(CallLog).filter(CallLog.phone_number_id == phone_number_id).count()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "calls": [
                {
                    "id": call.id,
                    "call_sid": call.call_sid,
                    "direction": call.direction.value if call.direction else None,
                    "status": call.status.value if call.status else None,
                    "duration_seconds": call.duration_seconds,
                    "start_time": call.start_time.isoformat() if call.start_time else None,
                    "end_time": call.end_time.isoformat() if call.end_time else None,
                    "turns_count": len(call.turns) if call.turns else 0,
                    "transcription_summary": call.transcription_summary,
                }
                for call in calls
            ]
        }
    except Exception as e:
        return {"error": f"Error al obtener llamadas: {str(e)}"}
    finally:
        db.close()


def get_calls_by_phone_number_str(
    phone_number: str,
    limit: int = 50,
    offset: int = 0
):
    """
    Obtiene las llamadas de un número telefónico específico por número de teléfono.
    """
    db = SessionLocal()
    try:
        from app.models.company_phone_number import CompanyPhoneNumber
        
        # Buscar el phone_number_id por el número de teléfono
        phone_number_obj = db.query(CompanyPhoneNumber).filter(
            CompanyPhoneNumber.phone_number == phone_number
        ).first()
        
        if not phone_number_obj:
            return {
                "total": 0,
                "limit": limit,
                "offset": offset,
                "calls": [],
                "message": f"No se encontró el número telefónico: {phone_number}"
            }
        
        # Cargar relaciones para evitar N+1 queries
        calls = db.query(CallLog).options(
            joinedload(CallLog.turns)
        ).filter(
            CallLog.phone_number_id == phone_number_obj.id
        ).order_by(desc(CallLog.start_time)).offset(offset).limit(limit).all()
        
        total = db.query(CallLog).filter(CallLog.phone_number_id == phone_number_obj.id).count()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "calls": [
                {
                    "id": call.id,
                    "call_sid": call.call_sid,
                    "direction": call.direction.value if call.direction else None,
                    "status": call.status.value if call.status else None,
                    "duration_seconds": call.duration_seconds,
                    "start_time": call.start_time.isoformat() if call.start_time else None,
                    "end_time": call.end_time.isoformat() if call.end_time else None,
                    "turns_count": len(call.turns) if call.turns else 0,
                    "transcription_summary": call.transcription_summary,
                }
                for call in calls
            ]
        }
    except Exception as e:
        return {"error": f"Error al obtener llamadas: {str(e)}"}
    finally:
        db.close()

