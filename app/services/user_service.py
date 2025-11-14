# app/services/user_service.py
from sqlalchemy.orm import Session
from app.persistance.db import SessionLocal
from app.models.user import User, UserRole
from app.config.security import hash_password
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone


def create_user(data: dict):
    """
    Crea un nuevo usuario para una empresa.
    """
    db = SessionLocal()
    try:
        company_id = data.get("company_id")
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        role = data.get("role", "admin")
        
        if not name or not email or not password:
            return {"error": "Nombre, email y contraseña son requeridos."}
        
        # Validar que el email no esté en uso
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            return {"error": "El email ya está registrado."}
        
        # Convertir role string a enum
        try:
            user_role = UserRole(role)
        except ValueError:
            user_role = UserRole.admin
        
        new_user = User(
            company_id=company_id,
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=user_role,
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "message": "Usuario creado correctamente.",
            "user_id": new_user.id,
            "company_id": company_id,
            "email": email,
            "role": user_role.value
        }
    except IntegrityError as e:
        db.rollback()
        return {"error": "Error de integridad al crear el usuario."}
    except Exception as e:
        db.rollback()
        return {"error": f"Error al crear usuario: {str(e)}"}
    finally:
        db.close()


def get_users_by_company(company_id: int, is_active: bool | None = None):
    """
    Obtiene todos los usuarios de una empresa.
    """
    db = SessionLocal()
    try:
        query = db.query(User).filter_by(company_id=company_id)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        
        users = query.order_by(User.name).all()
        
        return {
            "company_id": company_id,
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                    "role": u.role.value,
                    "is_active": u.is_active,
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
            "count": len(users)
        }
    except Exception as e:
        return {"error": f"Error al obtener usuarios: {str(e)}"}
    finally:
        db.close()


def get_user_by_id(user_id: int):
    """
    Obtiene un usuario por su ID.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return {"error": "Usuario no encontrado"}
        
        return {
            "id": user.id,
            "company_id": user.company_id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    except Exception as e:
        return {"error": f"Error al obtener usuario: {str(e)}"}
    finally:
        db.close()


def deactivate_user(user_id: int):
    """
    Desactiva un usuario individual.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return {"error": "Usuario no encontrado"}
        
        user.is_active = False
        db.commit()
        
        return {
            "message": "Usuario desactivado correctamente.",
            "user_id": user_id
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al desactivar usuario: {str(e)}"}
    finally:
        db.close()


def activate_user(user_id: int):
    """
    Activa un usuario individual.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return {"error": "Usuario no encontrado"}
        
        user.is_active = True
        db.commit()
        
        return {
            "message": "Usuario activado correctamente.",
            "user_id": user_id
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al activar usuario: {str(e)}"}
    finally:
        db.close()


def delete_user(user_id: int):
    """
    Elimina permanentemente un usuario.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return {"error": "Usuario no encontrado"}
        
        # No permitir eliminar superadmin
        if user.role == UserRole.superadmin:
            return {"error": "No se puede eliminar un superadministrador"}
        
        db.delete(user)
        db.commit()
        
        return {
            "message": "Usuario eliminado permanentemente.",
            "user_id": user_id
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al eliminar usuario: {str(e)}"}
    finally:
        db.close()


def update_user(user_id: int, data: dict):
    """
    Actualiza un usuario existente.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return {"error": "Usuario no encontrado"}
        
        # Actualizar campos permitidos
        if "name" in data:
            user.name = data["name"]
        if "email" in data:
            # Verificar que el email no esté en uso por otro usuario
            existing = db.query(User).filter(User.email == data["email"], User.id != user_id).first()
            if existing:
                return {"error": "El email ya está en uso por otro usuario"}
            user.email = data["email"]
        if "password" in data:
            user.password_hash = hash_password(data["password"])
        if "role" in data:
            try:
                user.role = UserRole(data["role"])
            except ValueError:
                return {"error": f"Rol inválido: {data['role']}"}
        if "is_active" in data:
            user.is_active = data["is_active"]
        
        db.commit()
        db.refresh(user)
        
        return {
            "message": "Usuario actualizado correctamente.",
            "user_id": user.id
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al actualizar usuario: {str(e)}"}
    finally:
        db.close()

