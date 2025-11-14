# app/services/contact_service.py
from sqlalchemy.orm import Session
from app.persistance.db import SessionLocal
from app.models.contact import Contact
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone


def create_contact(data: dict):
    """
    Crea un nuevo contacto para una empresa.
    """
    db = SessionLocal()
    try:
        company_id = data.get("company_id")
        name = data.get("name")
        phone_number = data.get("phone_number")
        email = data.get("email")
        description = data.get("description")
        notes = data.get("notes")
        preferred_call_time_start = data.get("preferred_call_time_start")
        preferred_call_time_end = data.get("preferred_call_time_end")
        timezone = data.get("timezone")
        tags = data.get("tags")
        
        if not name or not phone_number:
            return {"error": "El nombre y número de teléfono son requeridos."}
        
        # Validar si ya existe un contacto con ese número para la empresa
        existing = db.query(Contact).filter_by(
            company_id=company_id,
            phone_number=phone_number
        ).first()
        if existing:
            return {"error": "Ya existe un contacto con ese número de teléfono para esta empresa."}
        
        new_contact = Contact(
            company_id=company_id,
            name=name,
            phone_number=phone_number,
            email=email,
            description=description,
            notes=notes,
            preferred_call_time_start=preferred_call_time_start,
            preferred_call_time_end=preferred_call_time_end,
            timezone=timezone,
            tags=tags,
            is_active=True
        )
        
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        
        return {
            "message": "Contacto creado correctamente.",
            "contact_id": new_contact.id,
            "company_id": company_id,
            "name": name,
            "phone_number": phone_number
        }
    except IntegrityError as e:
        db.rollback()
        return {"error": "Error de integridad al crear el contacto."}
    except Exception as e:
        db.rollback()
        return {"error": f"Error al crear contacto: {str(e)}"}
    finally:
        db.close()


def get_contacts_by_company(company_id: int, is_active: bool = True):
    """
    Obtiene todos los contactos de una empresa.
    """
    db = SessionLocal()
    try:
        query = db.query(Contact).filter_by(company_id=company_id)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        
        contacts = query.order_by(Contact.name).all()
        
        return {
            "company_id": company_id,
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "phone_number": c.phone_number,
                    "email": c.email,
                    "description": c.description,
                    "notes": c.notes,
                    "preferred_call_time_start": c.preferred_call_time_start.isoformat() if c.preferred_call_time_start else None,
                    "preferred_call_time_end": c.preferred_call_time_end.isoformat() if c.preferred_call_time_end else None,
                    "timezone": c.timezone,
                    "tags": c.tags.split(",") if c.tags else [],
                    "is_active": c.is_active,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in contacts
            ],
            "count": len(contacts)
        }
    except Exception as e:
        return {"error": f"Error al obtener contactos: {str(e)}"}
    finally:
        db.close()


def get_contact_by_id(contact_id: int):
    """
    Obtiene un contacto por su ID.
    """
    db = SessionLocal()
    try:
        contact = db.query(Contact).filter_by(id=contact_id).first()
        if not contact:
            return {"error": "Contacto no encontrado"}
        
        return {
            "id": contact.id,
            "company_id": contact.company_id,
            "name": contact.name,
            "phone_number": contact.phone_number,
            "email": contact.email,
            "description": contact.description,
            "notes": contact.notes,
            "preferred_call_time_start": contact.preferred_call_time_start.isoformat() if contact.preferred_call_time_start else None,
            "preferred_call_time_end": contact.preferred_call_time_end.isoformat() if contact.preferred_call_time_end else None,
            "timezone": contact.timezone,
            "tags": contact.tags.split(",") if contact.tags else [],
            "is_active": contact.is_active,
            "created_at": contact.created_at.isoformat() if contact.created_at else None,
            "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
        }
    except Exception as e:
        return {"error": f"Error al obtener contacto: {str(e)}"}
    finally:
        db.close()


def update_contact(contact_id: int, data: dict):
    """
    Actualiza un contacto existente.
    """
    db = SessionLocal()
    try:
        contact = db.query(Contact).filter_by(id=contact_id).first()
        if not contact:
            return {"error": "Contacto no encontrado"}
        
        # Actualizar campos permitidos
        if "name" in data:
            contact.name = data["name"]
        if "phone_number" in data:
            contact.phone_number = data["phone_number"]
        if "email" in data:
            contact.email = data["email"]
        if "description" in data:
            contact.description = data["description"]
        if "notes" in data:
            contact.notes = data["notes"]
        if "preferred_call_time_start" in data:
            contact.preferred_call_time_start = data["preferred_call_time_start"]
        if "preferred_call_time_end" in data:
            contact.preferred_call_time_end = data["preferred_call_time_end"]
        if "timezone" in data:
            contact.timezone = data["timezone"]
        if "tags" in data:
            contact.tags = data["tags"]
        if "is_active" in data:
            contact.is_active = data["is_active"]
        
        contact.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(contact)
        
        return {
            "message": "Contacto actualizado correctamente.",
            "contact_id": contact.id
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al actualizar contacto: {str(e)}"}
    finally:
        db.close()


def delete_contact(contact_id: int):
    """
    Elimina (desactiva) un contacto.
    """
    db = SessionLocal()
    try:
        contact = db.query(Contact).filter_by(id=contact_id).first()
        if not contact:
            return {"error": "Contacto no encontrado"}
        
        contact.is_active = False
        contact.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        
        return {
            "message": "Contacto desactivado correctamente.",
            "contact_id": contact_id
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al desactivar contacto: {str(e)}"}
    finally:
        db.close()


def hard_delete_contact(contact_id: int):
    """
    Elimina permanentemente un contacto de la base de datos.
    """
    db = SessionLocal()
    try:
        contact = db.query(Contact).filter_by(id=contact_id).first()
        if not contact:
            return {"error": "Contacto no encontrado"}
        
        db.delete(contact)
        db.commit()
        
        return {
            "message": "Contacto eliminado permanentemente.",
            "contact_id": contact_id
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al eliminar contacto: {str(e)}"}
    finally:
        db.close()

