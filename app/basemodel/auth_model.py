from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuthUser(BaseModel):
    """Modelo para serializar datos del usuario autenticado."""
    id: int
    name: str
    email: str
    role: str
    company_id: Optional[int] = None
    is_active: bool
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True