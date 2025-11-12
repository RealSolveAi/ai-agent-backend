# app/routers/company_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.services.company_service import register_company_and_admin

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
async def register_company(request: RegisterCompanyRequest):
    result = register_company_and_admin(request.dict())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
