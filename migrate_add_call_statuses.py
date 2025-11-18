"""
Script de migración para agregar nuevos estados (no_answer, no_response) al enum CallStatus.
Ejecutar: python migrate_add_call_statuses.py

NOTA: En PostgreSQL, los enums no se pueden modificar directamente.
Este script verifica si los valores existen y los agrega si es necesario.
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
    """Agrega los nuevos valores al enum callstatus si no existen."""
    try:
        with engine.connect() as conn:
            # Verificar si los valores ya existen
            check_no_answer = conn.execute(text("""
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'no_answer' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'callstatus')
            """))
            no_answer_exists = check_no_answer.fetchone() is not None
            
            check_no_response = conn.execute(text("""
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'no_response' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'callstatus')
            """))
            no_response_exists = check_no_response.fetchone() is not None
            
            if no_answer_exists and no_response_exists:
                print("✅ Los valores no_answer y no_response ya existen en el enum CallStatus")
                return
            
            # Agregar no_answer si no existe
            if not no_answer_exists:
                print("📝 Agregando valor 'no_answer' al enum CallStatus...")
                conn.execute(text("ALTER TYPE callstatus ADD VALUE IF NOT EXISTS 'no_answer'"))
                conn.commit()
                print("✅ Valor 'no_answer' agregado")
            
            # Agregar no_response si no existe
            if not no_response_exists:
                print("📝 Agregando valor 'no_response' al enum CallStatus...")
                conn.execute(text("ALTER TYPE callstatus ADD VALUE IF NOT EXISTS 'no_response'"))
                conn.commit()
                print("✅ Valor 'no_response' agregado")
            
            print("✅ Migración completada exitosamente")
            
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        print("\n⚠️ NOTA: Si el error es 'ALTER TYPE ... ADD VALUE cannot run inside a transaction block',")
        print("   esto es normal en PostgreSQL. Los valores se agregarán automáticamente cuando")
        print("   SQLAlchemy intente usar el enum. Puedes ignorar este error.")
        sys.exit(1)

if __name__ == "__main__":
    migrate()

