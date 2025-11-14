# app/routers/user_router.py
from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.user_service import (
    create_user,
    get_users_by_company,
    get_user_by_id,
    deactivate_user,
    activate_user,
    delete_user,
    update_user
)
from app.routers.auth_router import get_superadmin, get_user_or_superadmin
from app.models.user import User, UserRole
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(prefix="/api/users", tags=["Users"])


class CreateUserRequest(BaseModel):
    company_id: int
    name: str
    email: EmailStr
    password: str
    role: str = "admin"  # admin, agent, viewer


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/")
async def create_user_endpoint(
    request: CreateUserRequest,
    current_user: User = Depends(get_superadmin)
):
    """
    Crea un nuevo usuario para una empresa.
    Solo accesible para superadministradores.
    """
    result = create_user(request.dict())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/company/{company_id}")
async def list_company_users(
    company_id: int,
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Lista todos los usuarios de una empresa.
    Superadmin puede acceder a cualquier empresa.
    Usuarios normales solo pueden ver usuarios de su empresa.
    """
    # Verificar que solo accede a su empresa (excepto superadmin)
    if current_user.role != UserRole.superadmin and company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a usuarios de esta empresa"
        )
    
    result = get_users_by_company(company_id, is_active)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{user_id}")
async def get_user_endpoint(
    user_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Obtiene un usuario por su ID.
    Superadmin puede acceder a cualquier usuario.
    Usuarios normales solo pueden ver usuarios de su empresa.
    """
    result = get_user_by_id(user_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    # Verificar que el usuario pertenece a la empresa del usuario actual (excepto superadmin)
    if current_user.role != UserRole.superadmin and result.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a este usuario"
        )
    
    return result


@router.put("/{user_id}")
async def update_user_endpoint(
    user_id: int,
    request: UpdateUserRequest,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Actualiza un usuario existente.
    Superadmin puede actualizar cualquier usuario.
    Usuarios normales solo pueden actualizar usuarios de su empresa.
    """
    # Verificar que el usuario pertenece a la empresa del usuario actual (excepto superadmin)
    user = get_user_by_id(user_id)
    if "error" in user:
        raise HTTPException(status_code=404, detail=user["error"])
    
    if current_user.role != UserRole.superadmin and user.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para actualizar este usuario"
        )
    
    result = update_user(user_id, request.dict(exclude_unset=True))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{user_id}/deactivate")
async def deactivate_user_endpoint(
    user_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Desactiva un usuario individual.
    Superadmin puede desactivar cualquier usuario.
    Usuarios normales solo pueden desactivar usuarios de su empresa.
    """
    # Verificar que el usuario pertenece a la empresa del usuario actual (excepto superadmin)
    user = get_user_by_id(user_id)
    if "error" in user:
        raise HTTPException(status_code=404, detail=user["error"])
    
    if current_user.role != UserRole.superadmin and user.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para desactivar este usuario"
        )
    
    result = deactivate_user(user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{user_id}/activate")
async def activate_user_endpoint(
    user_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Activa un usuario individual.
    Superadmin puede activar cualquier usuario.
    Usuarios normales solo pueden activar usuarios de su empresa.
    """
    # Verificar que el usuario pertenece a la empresa del usuario actual (excepto superadmin)
    user = get_user_by_id(user_id)
    if "error" in user:
        raise HTTPException(status_code=404, detail=user["error"])
    
    if current_user.role != UserRole.superadmin and user.get("company_id") != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para activar este usuario"
        )
    
    result = activate_user(user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/{user_id}")
async def delete_user_endpoint(
    user_id: int,
    current_user: User = Depends(get_superadmin)
):
    """
    Elimina permanentemente un usuario.
    Solo accesible para superadministradores.
    """
    result = delete_user(user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

