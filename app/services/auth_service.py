# app/services/auth_service.py
from sqlalchemy.orm import Session
from app.basemodel.auth_model import AuthUser
from app.persistance.db import SessionLocal
from app.models.user import User
from app.config.security import verify_password, create_access_token, hash_password
from datetime import datetime, timezone


def authenticate_user(email: str, password: str):
    """
    Autentica un usuario y retorna el usuario si las credenciales son correctas.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        # Verificar que la empresa del usuario esté activa (si tiene empresa)
        if user.company_id:
            from app.models.company import Company
            company = db.query(Company).filter(Company.id == user.company_id).first()
            if company and not company.is_active:
                return None  # Empresa desactivada, usuario no puede iniciar sesión
        
        if not verify_password(password, user.password_hash):
            return None
        
        # Actualizar último login
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        
        # Serializar datos del usuario antes de cerrar la sesión
        auth_user = AuthUser(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role.value,
            company_id=user.company_id,
            is_active=user.is_active,
            last_login=user.last_login
        )
        
        return auth_user
    except Exception as e:
        print(f"Error en autenticación: {e}")
        return None
    finally:
        db.close()


def get_user_by_id(user_id: int):
    """
    Obtiene un usuario por su ID.
    """
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def get_user_by_email(email: str):
    """
    Obtiene un usuario por su email.
    """
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def logout_user(user_id: int):
    """
    Registra el logout de un usuario actualizando last_logout.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "Usuario no encontrado"}
        
        user.last_logout = datetime.now(timezone.utc)
        db.commit()
        
        return {
            "message": "Logout exitoso",
            "user_id": user_id,
            "logged_out_at": user.last_logout.isoformat()
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al registrar logout: {str(e)}"}
    finally:
        db.close()

