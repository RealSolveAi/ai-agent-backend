# app/routers/contact_router.py
from fastapi import APIRouter, HTTPException, Query, Depends
from app.services.contact_service import (
    create_contact,
    get_contacts_by_company,
    get_contact_by_id,
    update_contact,
    delete_contact,
    hard_delete_contact
)
from app.routers.auth_router import get_current_user_with_company, get_user_or_superadmin
from app.models.user import User, UserRole
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
async def create_contact_endpoint(
    request: CreateContactRequest,
    current_user: User = Depends(get_user_or_superadmin)
):
    """Crea un nuevo contacto. Superadmin puede crear para cualquier empresa."""
    # Verificar que el contacto se crea para la empresa del usuario (excepto superadmin)
    if current_user.role != UserRole.superadmin and request.company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No puedes crear contactos para otras empresas"
        )
    
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
    is_active: Optional[bool] = Query(True),
    current_user: User = Depends(get_user_or_superadmin)
):
    """Lista todos los contactos de una empresa. Superadmin puede acceder a cualquier empresa."""
    # Verificar que solo accede a su empresa (excepto superadmin)
    if current_user.role != UserRole.superadmin and company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a contactos de esta empresa"
        )
    
    result = get_contacts_by_company(company_id, is_active)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{contact_id}")
async def get_contact_endpoint(
    contact_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """Obtiene un contacto por su ID. Superadmin puede acceder a cualquier contacto."""
    result = get_contact_by_id(contact_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    # Verificar que el contacto pertenece a la empresa del usuario (excepto superadmin)
    if current_user.role != UserRole.superadmin and result.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a este contacto"
        )
    
    return result


@router.put("/{contact_id}")
async def update_contact_endpoint(
    contact_id: int,
    request: UpdateContactRequest,
    current_user: User = Depends(get_user_or_superadmin)
):
    """Actualiza un contacto existente. Superadmin puede actualizar cualquier contacto."""
    # Verificar que el contacto pertenece a la empresa del usuario (excepto superadmin)
    contact = get_contact_by_id(contact_id)
    if "error" in contact:
        raise HTTPException(status_code=404, detail=contact["error"])
    
    if current_user.role != UserRole.superadmin and contact.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para actualizar este contacto"
        )
    
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


@router.post("/{contact_id}/deactivate")
async def deactivate_contact_endpoint(
    contact_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """Desactiva un contacto. Superadmin puede desactivar cualquier contacto."""
    # Verificar que el contacto pertenece a la empresa del usuario (excepto superadmin)
    contact = get_contact_by_id(contact_id)
    if "error" in contact:
        raise HTTPException(status_code=404, detail=contact["error"])
    
    if current_user.role != UserRole.superadmin and contact.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para desactivar este contacto"
        )
    
    result = delete_contact(contact_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/{contact_id}")
async def delete_contact_endpoint(
    contact_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Elimina permanentemente un contacto.
    Superadmin puede eliminar cualquier contacto.
    Usuarios normales solo pueden eliminar contactos de su empresa.
    ⚠️ ADVERTENCIA: Esta acción es irreversible.
    """
    # Verificar que el contacto pertenece a la empresa del usuario (excepto superadmin)
    contact = get_contact_by_id(contact_id)
    if "error" in contact:
        raise HTTPException(status_code=404, detail=contact["error"])
    
    if current_user.role != UserRole.superadmin and contact.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para eliminar este contacto"
        )
    
    result = hard_delete_contact(contact_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

