# app/routers/phone_number_router.py
from fastapi import APIRouter, HTTPException
from app.models.company_phone_number import NumberType
from app.services.phone_number_service import register_phone_number
from pydantic import BaseModel

router = APIRouter(prefix="/phone", tags=["Phone Numbers"])

class RegisterPhoneNumberRequest(BaseModel):
    company_id: int
    phone_number: str
    friendly_name: str | None = None
    type: NumberType = NumberType.both
    twilio_sid: str | None = None

@router.post("/register")
async def register_phone_number_endpoint(request: RegisterPhoneNumberRequest):
    result = register_phone_number(request.dict())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/company/{company_id}")
async def get_company_phone_numbers(company_id: int):
    """Obtiene todos los números telefónicos de una empresa."""
    from app.services.phone_number_service import get_phone_numbers_by_company
    result = get_phone_numbers_by_company(company_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result