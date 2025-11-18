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
    remember_me: bool = False  # Si es True, el token expira en 30 días


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Tiempo de expiración en segundos
    expires_at: str  # Fecha de expiración ISO format
    remember_me: bool
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
    access_token = create_access_token(token_data, remember_me=request.remember_me)
    
    # Calcular fecha de expiración para la respuesta
    from datetime import datetime, timedelta
    from app.config.security import REMEMBER_ME_EXPIRE_DAYS, ACCESS_TOKEN_EXPIRE_MINUTES
    if request.remember_me:
        expires_in = REMEMBER_ME_EXPIRE_DAYS * 24 * 60 * 60  # segundos
        expires_at = datetime.utcnow() + timedelta(days=REMEMBER_ME_EXPIRE_DAYS)
    else:
        expires_in = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # segundos
        expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,  # Tiempo de expiración en segundos
        "expires_at": expires_at.isoformat(),  # Fecha de expiración
        "remember_me": request.remember_me,
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
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "last_logout": current_user.last_logout.isoformat() if current_user.last_logout else None
    }


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Cierra la sesión del usuario actual.
    Registra el logout en la base de datos.
    
    Nota: Con JWT stateless, el token sigue siendo válido hasta su expiración.
    El cliente debe eliminar el token del almacenamiento local.
    """
    from app.services.auth_service import logout_user
    
    result = logout_user(current_user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        "message": "Sesión cerrada exitosamente",
        "logged_out_at": result["logged_out_at"]
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

