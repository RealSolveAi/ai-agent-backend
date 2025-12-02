# app/routers/agent_profile_router.py
from fastapi import APIRouter, HTTPException, Depends
from app.services.agent_profile_service import (
    create_agent_profile,
    get_agent_profiles_by_company,
    get_agent_profile_by_id,
    update_agent_profile,
    delete_agent_profile
)
from app.routers.auth_router import get_current_user, get_user_or_superadmin
from app.models.user import User
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/agent-profiles", tags=["Agent Profiles"])


class CreateAgentProfileRequest(BaseModel):
    company_id: int
    name: str
    voice: Optional[str] = "coral"
    temperature: Optional[float] = 0.8
    prompt: Optional[str] = None
    working_hours: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = True


class UpdateAgentProfileRequest(BaseModel):
    name: Optional[str] = None
    voice: Optional[str] = None
    temperature: Optional[float] = None
    prompt: Optional[str] = None
    working_hours: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/")
async def create_agent_profile_endpoint(
    request: CreateAgentProfileRequest,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Crea un nuevo perfil de agente para una empresa.
    Requiere autenticación.
    """
    # Verificar que el usuario tenga acceso a la empresa (si no es superadmin)
    if current_user.role.value != "superadmin":
        if current_user.company_id != request.company_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta empresa")
    
    result = create_agent_profile(request.dict())
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/company/{company_id}")
async def get_agent_profiles_by_company_endpoint(
    company_id: int,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Obtiene todos los perfiles de agente de una empresa.
    Requiere autenticación.
    """
    # Verificar que el usuario tenga acceso a la empresa (si no es superadmin)
    if current_user.role.value != "superadmin":
        if current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta empresa")
    
    result = get_agent_profiles_by_company(company_id, is_active)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/{agent_profile_id}")
async def get_agent_profile_endpoint(
    agent_profile_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Obtiene un perfil de agente por su ID.
    Requiere autenticación.
    """
    result = get_agent_profile_by_id(agent_profile_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    # Verificar que el usuario tenga acceso a la empresa del agente (si no es superadmin)
    if current_user.role.value != "superadmin":
        if current_user.company_id != result.get("company_id"):
            raise HTTPException(status_code=403, detail="No tienes acceso a este perfil de agente")
    
    return result


@router.put("/{agent_profile_id}")
async def update_agent_profile_endpoint(
    agent_profile_id: int,
    request: UpdateAgentProfileRequest,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Actualiza un perfil de agente.
    Requiere autenticación.
    """
    # Primero obtener el perfil para verificar permisos
    profile = get_agent_profile_by_id(agent_profile_id)
    if "error" in profile:
        raise HTTPException(status_code=404, detail=profile["error"])
    
    # Verificar que el usuario tenga acceso a la empresa (si no es superadmin)
    if current_user.role.value != "superadmin":
        if current_user.company_id != profile.get("company_id"):
            raise HTTPException(status_code=403, detail="No tienes acceso a este perfil de agente")
    
    result = update_agent_profile(agent_profile_id, request.dict(exclude_unset=True))
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.delete("/{agent_profile_id}")
async def delete_agent_profile_endpoint(
    agent_profile_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """
    Elimina un perfil de agente.
    Requiere autenticación.
    """
    # Primero obtener el perfil para verificar permisos
    profile = get_agent_profile_by_id(agent_profile_id)
    if "error" in profile:
        raise HTTPException(status_code=404, detail=profile["error"])
    
    # Verificar que el usuario tenga acceso a la empresa (si no es superadmin)
    if current_user.role.value != "superadmin":
        if current_user.company_id != profile.get("company_id"):
            raise HTTPException(status_code=403, detail="No tienes acceso a este perfil de agente")
    
    result = delete_agent_profile(agent_profile_id)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

