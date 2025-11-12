# app/routers/call_router.py
from fastapi import APIRouter, HTTPException, Query
from app.services.call_service import (
    get_calls_by_company,
    get_call_detail,
    get_calls_by_phone_number,
    get_calls_by_phone_number_str
)
from typing import Optional

router = APIRouter(prefix="/api/calls", tags=["Calls"])


@router.get("/company/{company_id}")
async def list_company_calls(
    company_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    phone_number_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None)
):
    """
    Lista las llamadas de una empresa.
    
    - **company_id**: ID de la empresa
    - **limit**: Número máximo de resultados (1-100)
    - **offset**: Número de resultados a saltar (paginación)
    - **phone_number_id**: Filtrar por número telefónico específico (opcional)
    - **status**: Filtrar por estado: 'initiated', 'in_progress', 'completed', 'failed' (opcional)
    """
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
async def get_call_by_id(call_id: int):
    """
    Obtiene el detalle completo de una llamada con su timeline de conversación.
    
    Incluye:
    - Información de la llamada (duración, estado, dirección, etc.)
    - Timeline completo con todos los turnos de conversación ordenados cronológicamente
    - Información de la empresa y número telefónico asociado
    """
    result = get_call_detail(call_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
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

