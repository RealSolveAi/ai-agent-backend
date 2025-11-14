# app/routers/auth_router.py
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from app.services.auth_service import authenticate_user
from app.config.security import create_access_token
from app.persistance.db import SessionLocal
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Inicia sesión y retorna un token JWT.
    """
    user = authenticate_user(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crear token JWT usando los datos del AuthUser
    token_data = {
        "sub": user.email,
        "user_id": user.id,
        "company_id": user.company_id,
        "role": user.role
    }
    access_token = create_access_token(token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.dict()
    }


# Dependencia para obtener el usuario actual
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependencia que valida el token JWT y retorna el usuario actual.
    """
    from app.config.security import decode_access_token
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado o inactivo",
            )
        return user
    finally:
        db.close()


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Obtiene la información del usuario autenticado.
    """
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role.value,
        "company_id": current_user.company_id,
        "company_name": current_user.company.name if current_user.company else None,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }


# Dependencia para verificar que el usuario pertenece a una empresa
def get_current_user_with_company(current_user: User = Depends(get_current_user)):
    """
    Dependencia que asegura que el usuario tiene una empresa asignada.
    Los superadmins pueden no tener empresa asignada.
    """
    from app.models.user import UserRole
    
    # Superadmin no necesita empresa
    if current_user.role == UserRole.superadmin:
        return current_user
    
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no tiene empresa asignada",
        )
    return current_user


# Dependencia para verificar que el usuario es superadmin
def get_superadmin(current_user: User = Depends(get_current_user)):
    """
    Dependencia que verifica que el usuario es superadmin.
    """
    from app.models.user import UserRole
    
    if current_user.role != UserRole.superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los superadministradores pueden realizar esta acción",
        )
    return current_user


# Dependencia que permite acceso a superadmin o usuarios de empresa
def get_user_or_superadmin(current_user: User = Depends(get_current_user)):
    """
    Dependencia que permite acceso a superadmin (sin restricción de empresa)
    o usuarios normales (con restricción de empresa).
    """
    from app.models.user import UserRole
    
    # Superadmin puede acceder a todo
    if current_user.role == UserRole.superadmin:
        return current_user
    
    # Usuarios normales deben tener empresa
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no tiene empresa asignada",
        )
    return current_user

