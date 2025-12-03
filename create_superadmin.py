# create_superadmin.py
# Script para crear un usuario superadmin en la base de datos
# Importar todos los modelos para que SQLAlchemy pueda resolver las relaciones
from app.models import (
    company,
    user,
    contact,
    call_log,
    call_turn,
    company_phone_number,
    agent_profile
)

from app.persistance.db import SessionLocal
from app.models.user import User, UserRole
from app.config.security import hash_password
from datetime import datetime, timezone

def create_superadmin():
    """
    Crea un usuario superadmin en la base de datos.
    """
    db = SessionLocal()
    try:
        # Datos del superadmin (puedes modificar estos valores)
        superadmin_email = "superadmin@realsolveai.com"
        superadmin_password = "SuperAdmin123+"  # Cambiar por una contraseña segura
        superadmin_name = "Super Administrador"
        
        # Verificar si ya existe
        existing = db.query(User).filter(User.email == superadmin_email).first()
        if existing:
            # Actualizar a superadmin si ya existe
            existing.role = UserRole.superadmin
            existing.company_id = None
            existing.is_active = True
            existing.password_hash = hash_password(superadmin_password)
            db.commit()
            print(f"✅ Usuario actualizado a superadmin: {superadmin_email}")
            return
        
        # Crear nuevo superadmin
        superadmin = User(
            company_id=None,  # Superadmin no tiene empresa
            name=superadmin_name,
            email=superadmin_email,
            password_hash=hash_password(superadmin_password),
            role=UserRole.superadmin,
            is_active=True
        )
        
        db.add(superadmin)
        db.commit()
        db.refresh(superadmin)
        
        print(f"✅ Superadmin creado exitosamente!")
        print(f"   Email: {superadmin_email}")
        print(f"   Password: {superadmin_password}")
        print(f"   ID: {superadmin.id}")
        print(f"\n⚠️  IMPORTANTE: Cambia la contraseña después del primer login!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear superadmin: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🛠️  Creando usuario superadmin...")
    create_superadmin()

