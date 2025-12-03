# app/services/company_service.py
from app.models.company import Company
from app.models.user import User, UserRole
from app.persistance.db import SessionLocal
from app.config.security import hash_password
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone


def register_company_and_admin(data: dict):
    """
    Registra una nueva empresa y su usuario administrador principal.
    """
    db = SessionLocal()
    try:
        company = Company(
            name=data["company_name"],
            email=data.get("company_email"),
            industry=data.get("industry"),
            country=data.get("country"),
            timezone=data.get("timezone")
        )
        db.add(company)
        db.commit()
        db.refresh(company)

        admin_user = User(
            company_id=company.id,
            name=data["admin_name"],
            email=data["admin_email"],
            password_hash=hash_password(data["admin_password"]),
            role=UserRole.admin
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        return {
            "message": "Empresa y usuario administrador creados correctamente.",
            "company_id": company.id,
            "admin_id": admin_user.id
        }
    except IntegrityError:
        db.rollback()
        return {"error": "El correo ya está registrado o la empresa ya existe."}
    finally:
        db.close()


def get_all_companies(limit: int = 100, offset: int = 0):
    """
    Obtiene todas las empresas (solo para superadmin).
    """
    db = SessionLocal()
    try:
        from sqlalchemy import desc
        companies = db.query(Company).order_by(desc(Company.created_at)).offset(offset).limit(limit).all()
        total = db.query(Company).count()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "companies": [
                {
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "industry": c.industry,
                    "country": c.country,
                    "timezone": c.timezone,
                    "status": c.status,
                    "is_active": c.is_active,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in companies
            ]
        }
    except Exception as e:
        return {"error": f"Error al obtener empresas: {str(e)}"}
    finally:
        db.close()


def get_company_by_id(company_id: int):
    """
    Obtiene una empresa por su ID (solo para superadmin).
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return {"error": "Empresa no encontrada"}
        
        return {
            "id": company.id,
            "name": company.name,
            "email": company.email,
            "industry": company.industry,
            "country": company.country,
            "timezone": company.timezone,
            "status": company.status,
            "is_active": company.is_active,
            "created_at": company.created_at.isoformat() if company.created_at else None,
            "updated_at": company.updated_at.isoformat() if company.updated_at else None,
        }
    except Exception as e:
        return {"error": f"Error al obtener empresa: {str(e)}"}
    finally:
        db.close()


def deactivate_company(company_id: int):
    """
    Desactiva una empresa y todos sus usuarios.
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return {"error": "Empresa no encontrada"}
        
        # Desactivar empresa
        company.is_active = False
        company.updated_at = datetime.now(timezone.utc)
        
        # Desactivar todos los usuarios de la empresa
        users = db.query(User).filter(User.company_id == company_id).all()
        for user in users:
            user.is_active = False
        
        db.commit()
        
        return {
            "message": f"Empresa y {len(users)} usuarios desactivados correctamente.",
            "company_id": company_id,
            "users_deactivated": len(users)
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al desactivar empresa: {str(e)}"}
    finally:
        db.close()


def activate_company(company_id: int):
    """
    Activa una empresa y todos sus usuarios.
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return {"error": "Empresa no encontrada"}
        
        # Activar empresa
        company.is_active = True
        company.updated_at = datetime.now(timezone.utc)
        
        # Activar todos los usuarios de la empresa
        users = db.query(User).filter(User.company_id == company_id).all()
        for user in users:
            user.is_active = True
        
        db.commit()
        
        return {
            "message": f"Empresa y {len(users)} usuarios activados correctamente.",
            "company_id": company_id,
            "users_activated": len(users)
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al activar empresa: {str(e)}"}
    finally:
        db.close()


def update_company(company_id: int, data: dict):
    """
    Actualiza una empresa existente.
    Solo permite actualizar campos específicos.
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return {"error": "Empresa no encontrada"}
        
        # Actualizar campos permitidos
        if "name" in data and data["name"]:
            company.name = data["name"]
        if "email" in data:
            company.email = data["email"]
        if "industry" in data:
            company.industry = data["industry"]
        if "country" in data:
            company.country = data["country"]
        if "timezone" in data:
            company.timezone = data["timezone"]
        if "status" in data:
            company.status = data["status"]
        if "is_active" in data:
            company.is_active = data["is_active"]
        
        # Actualizar timestamp
        company.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(company)
        
        return {
            "message": "Empresa actualizada correctamente.",
            "company_id": company.id,
            "company": {
                "id": company.id,
                "name": company.name,
                "email": company.email,
                "industry": company.industry,
                "country": company.country,
                "timezone": company.timezone,
                "status": company.status,
                "is_active": company.is_active,
                "updated_at": company.updated_at.isoformat() if company.updated_at else None,
            }
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al actualizar empresa: {str(e)}"}
    finally:
        db.close()


def delete_company(company_id: int):
    """
    Elimina permanentemente una empresa y todos sus datos relacionados.
    CASCADE eliminará usuarios, números telefónicos, contactos y llamadas.
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return {"error": "Empresa no encontrada"}
        
        company_name = company.name
        
        # Verificar si hay datos relacionados antes de eliminar (para mejor mensaje de error)
        from sqlalchemy import func
        from app.models.user import User
        from app.models.company_phone_number import CompanyPhoneNumber
        from app.models.contact import Contact
        from app.models.call_log import CallLog
        from app.models.agent_profile import AgentProfile
        
        user_count = db.query(func.count(User.id)).filter(User.company_id == company_id).scalar() or 0
        phone_count = db.query(func.count(CompanyPhoneNumber.id)).filter(CompanyPhoneNumber.company_id == company_id).scalar() or 0
        contact_count = db.query(func.count(Contact.id)).filter(Contact.company_id == company_id).scalar() or 0
        call_count = db.query(func.count(CallLog.id)).filter(CallLog.company_id == company_id).scalar() or 0
        agent_count = db.query(func.count(AgentProfile.id)).filter(AgentProfile.company_id == company_id).scalar() or 0
        
        # Eliminar empresa (CASCADE eliminará todo lo relacionado)
        db.delete(company)
        db.commit()
        
        return {
            "message": f"Empresa '{company_name}' y todos sus datos relacionados eliminados permanentemente.",
            "company_id": company_id,
            "deleted_data": {
                "users": user_count,
                "phone_numbers": phone_count,
                "contacts": contact_count,
                "calls": call_count,
                "agent_profiles": agent_count
            }
        }
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e)
        # Proporcionar un mensaje más específico
        if "foreign key constraint" in error_msg.lower() or "violates foreign key" in error_msg.lower():
            return {
                "error": "No se puede eliminar la empresa porque tiene datos relacionados que no pueden ser eliminados. "
                        "Asegúrate de que todas las relaciones tengan CASCADE configurado correctamente."
            }
        return {"error": f"Error de integridad al eliminar empresa: {error_msg}"}
    except Exception as e:
        db.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Error al eliminar empresa {company_id}: {error_details}")
        return {"error": f"Error al eliminar empresa: {str(e)}"}
    finally:
        db.close()
