"""
Script de migración para agregar las tablas de appointments y appointment_reminders.

Ejecutar:
    python migrate_add_appointments.py
"""

import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def migrate():
    """Crea las tablas de appointments y appointment_reminders si no existen."""
    
    print("🔄 Iniciando migración de appointments...")
    
    try:
        # Obtener URL de la base de datos
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL no está configurada en el archivo .env")
        
        print(f"📊 Conectando a la base de datos...")
        
        # Crear engine
        engine = create_engine(database_url)
        
        # Verificar si las tablas ya existen
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN ('appointments', 'appointment_reminders')"
            ))
            existing_tables = [row[0] for row in result]
        
        if 'appointments' in existing_tables and 'appointment_reminders' in existing_tables:
            print("⚠️  Las tablas 'appointments' y 'appointment_reminders' ya existen.")
            response = input("¿Deseas recrearlas? Esto eliminará todos los datos. (s/N): ")
            if response.lower() != 's':
                print("❌ Migración cancelada.")
                return
            
            # Eliminar tablas existentes
            print("🗑️  Eliminando tablas existentes...")
            with engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS appointment_reminders CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS appointments CASCADE"))
                conn.commit()
        
        # Importar modelos solo después de configurar el engine
        from app.persistance.db import Base
        from app.models.appointment import Appointment
        from app.models.appointment_reminder import AppointmentReminder
        
        # Crear solo las tablas nuevas
        print("✨ Creando tablas de appointments...")
        Appointment.__table__.create(engine, checkfirst=True)
        AppointmentReminder.__table__.create(engine, checkfirst=True)
        
        print("✅ Migración completada exitosamente!")
        print("📋 Tablas creadas:")
        print("   - appointments")
        print("   - appointment_reminders")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    migrate()
