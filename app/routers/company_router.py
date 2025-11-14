# app/routers/company_router.py
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr
from app.services.company_service import (
    register_company_and_admin,
    get_all_companies,
    get_company_by_id,
    deactivate_company,
    activate_company,
    delete_company
)
from app.routers.auth_router import get_superadmin, get_user_or_superadmin
from app.models.user import User
from typing import Optional

router = APIRouter(prefix="/company", tags=["Company & Users"])

class RegisterCompanyRequest(BaseModel):
    company_name: str
    company_email: EmailStr
    industry: str | None = None
    country: str | None = None
    timezone: str | None = "America/Bogota"
    admin_name: str
    admin_email: EmailStr
    admin_password: str

@router.post("/register")
async def register_company(
    request: RegisterCompanyRequest,
    current_user: User = Depends(get_superadmin)
):
    """
    Registra una nueva empresa y su usuario administrador.
    Solo accesible para superadministradores.
    """
    result = register_company_and_admin(request.dict())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/")
async def list_all_companies(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_superadmin)
):
    """
    Lista todas las empresas.
    Solo accesible para superadministradores.
    """
    result = get_all_companies(limit=limit, offset=offset)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{company_id}")
async def get_company(
    company_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Obtiene una empresa por su ID.
    Superadmin puede acceder a cualquier empresa.
    Usuarios normales solo pueden acceder a su propia empresa.
    """
    # Verificar que solo accede a su empresa (excepto superadmin)
    from app.models.user import UserRole
    if current_user.role != UserRole.superadmin and company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a esta empresa"
        )
    
    result = get_company_by_id(company_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{company_id}/deactivate")
async def deactivate_company_endpoint(
    company_id: int,
    current_user: User = Depends(get_superadmin)
):
    """
    Desactiva una empresa y todos sus usuarios.
    Solo accesible para superadministradores.
    """
    result = deactivate_company(company_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{company_id}/activate")
async def activate_company_endpoint(
    company_id: int,
    current_user: User = Depends(get_superadmin)
):
    """
    Activa una empresa y todos sus usuarios.
    Solo accesible para superadministradores.
    """
    result = activate_company(company_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/{company_id}")
async def delete_company_endpoint(
    company_id: int,
    current_user: User = Depends(get_superadmin)
):
    """
    Elimina permanentemente una empresa y todos sus datos relacionados.
    Solo accesible para superadministradores.
    ⚠️ ADVERTENCIA: Esta acción es irreversible y eliminará:
    - Todos los usuarios de la empresa
    - Todos los números telefónicos
    - Todos los contactos
    - Todas las llamadas y turnos de conversación
    """
    result = delete_company(company_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
