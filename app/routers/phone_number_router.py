# app/routers/phone_number_router.py
from fastapi import APIRouter, HTTPException, Depends
from app.models.company_phone_number import NumberType
from app.services.phone_number_service import register_phone_number
from app.routers.auth_router import get_current_user_with_company, get_user_or_superadmin
from app.models.user import User, UserRole
from pydantic import BaseModel

router = APIRouter(prefix="/phone", tags=["Phone Numbers"])

class RegisterPhoneNumberRequest(BaseModel):
    company_id: int
    phone_number: str
    friendly_name: str | None = None
    type: NumberType = NumberType.both
    twilio_sid: str | None = None

@router.post("/register")
async def register_phone_number_endpoint(
    request: RegisterPhoneNumberRequest,
    current_user: User = Depends(get_user_or_superadmin)
):
    """Registra un número telefónico. Superadmin puede registrar para cualquier empresa."""
    # Verificar que el número se registra para la empresa del usuario (excepto superadmin)
    if current_user.role != UserRole.superadmin and request.company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No puedes registrar números telefónicos para otras empresas"
        )
    
    result = register_phone_number(request.dict())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/company/{company_id}")
async def get_company_phone_numbers(
    company_id: int,
    current_user: User = Depends(get_user_or_superadmin)
):
    """Obtiene todos los números telefónicos de una empresa. Superadmin puede acceder a cualquier empresa."""
    # Verificar que solo accede a su empresa (excepto superadmin)
    if current_user.role != UserRole.superadmin and company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a números telefónicos de esta empresa"
        )
    
    from app.services.phone_number_service import get_phone_numbers_by_company
    result = get_phone_numbers_by_company(company_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result