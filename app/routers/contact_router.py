# app/routers/contact_router.py
from fastapi import APIRouter, HTTPException, Query
from app.services.contact_service import (
    create_contact,
    get_contacts_by_company,
    get_contact_by_id,
    update_contact,
    delete_contact
)
from pydantic import BaseModel
from typing import Optional
from datetime import time

router = APIRouter(prefix="/api/contacts", tags=["Contacts"])


class CreateContactRequest(BaseModel):
    company_id: int
    name: str
    phone_number: str
    email: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    preferred_call_time_start: Optional[str] = None  # Formato "HH:MM:SS"
    preferred_call_time_end: Optional[str] = None
    timezone: Optional[str] = None
    tags: Optional[str] = None  # Separados por comas


class UpdateContactRequest(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    preferred_call_time_start: Optional[str] = None
    preferred_call_time_end: Optional[str] = None
    timezone: Optional[str] = None
    tags: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/")
async def create_contact_endpoint(request: CreateContactRequest):
    """Crea un nuevo contacto para una empresa."""
    data = request.dict()
    
    # Convertir strings de tiempo a objetos time
    if data.get("preferred_call_time_start"):
        try:
            time_parts = data["preferred_call_time_start"].split(":")
            data["preferred_call_time_start"] = time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        except:
            data["preferred_call_time_start"] = None
    
    if data.get("preferred_call_time_end"):
        try:
            time_parts = data["preferred_call_time_end"].split(":")
            data["preferred_call_time_end"] = time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        except:
            data["preferred_call_time_end"] = None
    
    result = create_contact(data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/company/{company_id}")
async def list_company_contacts(
    company_id: int,
    is_active: Optional[bool] = Query(True)
):
    """Lista todos los contactos de una empresa."""
    result = get_contacts_by_company(company_id, is_active)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{contact_id}")
async def get_contact_endpoint(contact_id: int):
    """Obtiene un contacto por su ID."""
    result = get_contact_by_id(contact_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.put("/{contact_id}")
async def update_contact_endpoint(contact_id: int, request: UpdateContactRequest):
    """Actualiza un contacto existente."""
    data = request.dict(exclude_unset=True)
    
    # Convertir strings de tiempo a objetos time
    if data.get("preferred_call_time_start"):
        try:
            time_parts = data["preferred_call_time_start"].split(":")
            data["preferred_call_time_start"] = time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        except:
            data["preferred_call_time_start"] = None
    
    if data.get("preferred_call_time_end"):
        try:
            time_parts = data["preferred_call_time_end"].split(":")
            data["preferred_call_time_end"] = time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        except:
            data["preferred_call_time_end"] = None
    
    result = update_contact(contact_id, data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/{contact_id}")
async def delete_contact_endpoint(contact_id: int):
    """Desactiva un contacto."""
    result = delete_contact(contact_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

