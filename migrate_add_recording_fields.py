"""
Script de migración para agregar recording_sid y recording_duration a call_logs.
Ejecutar: python migrate_add_recording_fields.py
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL no encontrada en las variables de entorno")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def migrate():
    """Agrega las columnas recording_sid y recording_duration a la tabla call_logs."""
    try:
        with engine.connect() as conn:
            # Verificar si las columnas ya existen
            check_sid = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'call_logs' AND column_name = 'recording_sid'
            """))
            sid_exists = check_sid.fetchone() is not None
            
            check_duration = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'call_logs' AND column_name = 'recording_duration'
            """))
            duration_exists = check_duration.fetchone() is not None
            
            if sid_exists and duration_exists:
                print("✅ Las columnas recording_sid y recording_duration ya existen")
                return
            
            # Agregar recording_sid si no existe
            if not sid_exists:
                print("📝 Agregando columna recording_sid...")
                conn.execute(text("""
                    ALTER TABLE call_logs 
                    ADD COLUMN recording_sid VARCHAR(255) NULL
                """))
                conn.commit()
                print("✅ Columna recording_sid agregada")
            
            # Agregar recording_duration si no existe
            if not duration_exists:
                print("📝 Agregando columna recording_duration...")
                conn.execute(text("""
                    ALTER TABLE call_logs 
                    ADD COLUMN recording_duration INTEGER NULL
                """))
                conn.commit()
                print("✅ Columna recording_duration agregada")
            
            print("✅ Migración completada exitosamente")
            
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()

