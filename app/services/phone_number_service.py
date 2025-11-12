from sqlalchemy.orm import Session
from app.persistance.db import SessionLocal
from app.models.company_phone_number import CompanyPhoneNumber, NumberType
from sqlalchemy.exc import IntegrityError


def register_phone_number(data: dict):
    """
    Registra un nuevo número telefónico y lo asocia a una empresa.
    """
    db = SessionLocal()
    try:
        company_id = data.get("company_id")
        phone_number = data.get("phone_number")
        friendly_name = data.get("friendly_name")
        number_type = data.get("type", "both")
        twilio_sid = data.get("twilio_sid")

        # Validar que se proporcione el número
        if not phone_number:
            return {"error": "El número telefónico es requerido."}

        # Validar si ya existe ese número
        existing = db.query(CompanyPhoneNumber).filter_by(phone_number=phone_number).first()
        if existing:
            return {"error": "El número ya está registrado."}

        # Convertir el tipo si es string
        if isinstance(number_type, str):
            try:
                number_type = NumberType(number_type)
            except ValueError:
                number_type = NumberType.both

        new_number = CompanyPhoneNumber(
            company_id=company_id,
            phone_number=phone_number,
            friendly_name=friendly_name,
            type=number_type,
            twilio_sid=twilio_sid
        )
        
        # Crear el número telefónico
        db.add(new_number)
        db.commit()
        db.refresh(new_number)

        return {
            "message": "Número telefónico registrado correctamente.",
            "number_id": new_number.id,
            "company_id": company_id,
            "phone_number": phone_number
        }
    except IntegrityError as e:
        db.rollback()
        return {"error": "El número ya está registrado o hay un error de integridad."}
    except Exception as e:
        db.rollback()
        return {"error": f"Error al registrar el número: {str(e)}"}
    finally:
        db.close()


def get_phone_numbers_by_company(company_id: int):
    """
    Obtiene todos los números telefónicos asociados a una empresa.
    """
    db = SessionLocal()
    try:
        phone_numbers = db.query(CompanyPhoneNumber).filter_by(company_id=company_id).all()
        return {
            "company_id": company_id,
            "phone_numbers": [
                {
                    "id": pn.id,
                    "phone_number": pn.phone_number,
                    "friendly_name": pn.friendly_name,
                    "type": pn.type.value if pn.type else None,
                    "twilio_sid": pn.twilio_sid,
                    "created_at": pn.created_at.isoformat() if pn.created_at else None
                }
                for pn in phone_numbers
            ],
            "count": len(phone_numbers)
        }
    except Exception as e:
        return {"error": f"Error al obtener números telefónicos: {str(e)}"}
    finally:
        db.close()
