# app/routers/call_router.py
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from app.services.call_service import (
    get_calls_by_company,
    get_all_calls,
    get_call_detail,
    get_calls_by_phone_number,
    get_calls_by_phone_number_str
)
from app.routers.auth_router import get_current_user_with_company, get_user_or_superadmin
from app.models.user import User, UserRole
from app.persistance.db import SessionLocal
from app.models.call_log import CallLog
from typing import Optional
import httpx
import os

router = APIRouter(prefix="/api/calls", tags=["Calls"])


@router.get("/")
async def list_my_company_calls(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    phone_number_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),  # Para superadmin
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Lista las llamadas.
    - Superadmin: puede ver todas las llamadas (opcionalmente filtrar por company_id)
    - Usuarios normales: ven solo llamadas de su empresa
    
    - **limit**: Número máximo de resultados (1-100)
    - **offset**: Número de resultados a saltar (paginación)
    - **phone_number_id**: Filtrar por número telefónico específico (opcional)
    - **status**: Filtrar por estado: 'initiated', 'in_progress', 'completed', 'failed' (opcional)
    - **company_id**: Filtrar por empresa (solo para superadmin, opcional)
    """
    # Superadmin puede ver todas las llamadas o filtrar por company_id
    if current_user.role == UserRole.superadmin:
        if company_id:
            # Filtrar por empresa específica
            result = get_calls_by_company(
                company_id=company_id,
                limit=limit,
                offset=offset,
                phone_number_id=phone_number_id,
                status=status
            )
        else:
            # Ver todas las llamadas
            result = get_all_calls(
                limit=limit,
                offset=offset,
                phone_number_id=phone_number_id,
                status=status
            )
    else:
        # Usuarios normales solo ven llamadas de su empresa
        result = get_calls_by_company(
            company_id=current_user.company_id,
            limit=limit,
            offset=offset,
            phone_number_id=phone_number_id,
            status=status
        )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/company/{company_id}")
async def list_company_calls(
    company_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    phone_number_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Lista las llamadas de una empresa.
    Superadmin puede acceder a cualquier empresa.
    Usuarios normales solo pueden acceder a llamadas de su propia empresa.
    
    - **company_id**: ID de la empresa
    - **limit**: Número máximo de resultados (1-100)
    - **offset**: Número de resultados a saltar (paginación)
    - **phone_number_id**: Filtrar por número telefónico específico (opcional)
    - **status**: Filtrar por estado: 'initiated', 'in_progress', 'completed', 'failed' (opcional)
    """
    # Verificar que el usuario solo acceda a su empresa (excepto superadmin)
    if current_user.role != UserRole.superadmin and company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a llamadas de esta empresa"
        )
    
    result = get_calls_by_company(
        company_id=company_id,
        limit=limit,
        offset=offset,
        phone_number_id=phone_number_id,
        status=status
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/{call_id}")
async def get_call_by_id(
    call_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Obtiene el detalle completo de una llamada con su timeline de conversación.
    Superadmin puede acceder a cualquier llamada.
    Usuarios normales solo pueden acceder a llamadas de su propia empresa.
    
    Incluye:
    - Información de la llamada (duración, estado, dirección, etc.)
    - Timeline completo con todos los turnos de conversación ordenados cronológicamente
    - Información de la empresa y número telefónico asociado
    """
    result = get_call_detail(call_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    # Verificar que la llamada pertenece a la empresa del usuario (excepto superadmin)
    call_company_id = result.get("company", {}).get("id")
    if current_user.role != UserRole.superadmin and call_company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a esta llamada"
        )
    
    return result


@router.get("/phone/id/{phone_number_id}")
async def list_phone_calls_by_id(
    phone_number_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Lista las llamadas de un número telefónico específico por ID.
    
    - **phone_number_id**: ID del número telefónico
    - **limit**: Número máximo de resultados (1-100)
    - **offset**: Número de resultados a saltar (paginación)
    """
    result = get_calls_by_phone_number(
        phone_number_id=phone_number_id,
        limit=limit,
        offset=offset
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/phone/{phone_number}")
async def list_phone_calls_by_number(
    phone_number: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Lista las llamadas de un número telefónico específico por número de teléfono.
    
    - **phone_number**: Número de teléfono (ej: +17869461585)
    - **limit**: Número máximo de resultados (1-100)
    - **offset**: Número de resultados a saltar (paginación)
    """
    result = get_calls_by_phone_number_str(
        phone_number=phone_number,
        limit=limit,
        offset=offset
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/{call_id}/recording")
async def download_call_recording(
    call_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Descarga el audio de la grabación de una llamada.
    El backend descarga el audio desde Twilio y lo sirve al frontend,
    evitando exponer las credenciales de Twilio.
    
    Superadmin puede acceder a cualquier grabación.
    Usuarios normales solo pueden acceder a grabaciones de su propia empresa.
    """
    db = SessionLocal()
    try:
        call = db.query(CallLog).filter(CallLog.id == call_id).first()
        if not call:
            raise HTTPException(status_code=404, detail="Llamada no encontrada")
        
        # Verificar permisos
        if current_user.role != UserRole.superadmin:
            if not call.company_id or call.company_id != current_user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permiso para acceder a esta grabación"
                )
        
        # Verificar que existe grabación
        if not call.recording_sid and not call.recording_url:
            raise HTTPException(
                status_code=404,
                detail="Esta llamada no tiene grabación disponible"
            )
        
        # Obtener el recording_sid
        recording_sid = call.recording_sid
        if not recording_sid and call.recording_url:
            # Extraer SID de la URL si no está guardado
            # Formato: https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Recordings/{RecordingSid}
            parts = call.recording_url.split('/Recordings/')
            if len(parts) > 1:
                recording_sid = parts[-1]
        
        if not recording_sid:
            raise HTTPException(
                status_code=404,
                detail="No se pudo obtener el SID de la grabación"
            )
        
        # Obtener credenciales de Twilio
        from app.services.twilio_service import twilio_client
        TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
        TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="Configuración de Twilio no encontrada"
            )
        
        # Construir URL de descarga de Twilio
        # Twilio requiere autenticación básica para descargar grabaciones
        recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Recordings/{recording_sid}.mp3"
        
        # Descargar el audio desde Twilio usando httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                recording_url,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error al descargar grabación de Twilio: {response.text}"
                )
            
            # Retornar el audio como streaming response
            return StreamingResponse(
                iter([response.content]),
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f'attachment; filename="recording_{call_id}_{recording_sid}.mp3"',
                    "Content-Length": str(len(response.content))
                }
            )
    finally:
        db.close()


@router.get("/recordings/list")
async def list_recordings(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    company_id: Optional[int] = Query(None),  # Para superadmin
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Lista todas las grabaciones disponibles.
    Superadmin puede ver todas las grabaciones o filtrar por company_id.
    Usuarios normales solo ven grabaciones de su empresa.
    
    - **limit**: Número máximo de resultados (1-100)
    - **offset**: Número de resultados a saltar (paginación)
    - **company_id**: Filtrar por empresa (solo para superadmin, opcional)
    """
    db = SessionLocal()
    try:
        from sqlalchemy import desc
        
        # Construir query base
        query = db.query(CallLog).filter(
            CallLog.recording_sid.isnot(None)
        )
        
        # Aplicar filtros según el rol
        if current_user.role == UserRole.superadmin:
            if company_id:
                query = query.filter(CallLog.company_id == company_id)
        else:
            # Usuarios normales solo ven grabaciones de su empresa
            query = query.filter(CallLog.company_id == current_user.company_id)
        
        # Ordenar por fecha de creación descendente
        query = query.order_by(desc(CallLog.created_at))
        
        # Contar total
        total = query.count()
        
        # Aplicar paginación
        calls = query.offset(offset).limit(limit).all()
        
        recordings = []
        for call in calls:
            recordings.append({
                "id": call.id,
                "call_sid": call.call_sid,
                "recording_sid": call.recording_sid,
                "recording_url": call.recording_url,
                "recording_duration": call.recording_duration,
                "direction": call.direction.value if call.direction else None,
                "status": call.status.value if call.status else None,
                "duration_seconds": call.duration_seconds,
                "start_time": call.start_time.isoformat() if call.start_time else None,
                "end_time": call.end_time.isoformat() if call.end_time else None,
                "company": {
                    "id": call.company.id if call.company else None,
                    "name": call.company.name if call.company else None,
                } if call.company else None,
                "phone_number": {
                    "id": call.phone_number.id if call.phone_number else None,
                    "phone_number": call.phone_number.phone_number if call.phone_number else None,
                    "friendly_name": call.phone_number.friendly_name if call.phone_number else None,
                } if call.phone_number else None,
                "contact": {
                    "id": call.contact.id if call.contact else None,
                    "name": call.contact.name if call.contact else None,
                    "phone_number": call.contact.phone_number if call.contact else None,
                } if call.contact else None,
            })
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "recordings": recordings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener grabaciones: {str(e)}")
    finally:
        db.close()

