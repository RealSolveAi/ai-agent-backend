# app/services/company_service.py
from app.models.company import Company
from app.models.user import User, UserRole
from app.persistance.db import SessionLocal
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError


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
            password_hash=generate_password_hash(data["admin_password"]),
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
