"""
Script de migración para agregar agent_profile_id a call_logs.
Ejecutar: python migrate_add_agent_profile_id_to_call_logs.py
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
    """Agrega la columna agent_profile_id a la tabla call_logs si no existe."""
    try:
        with engine.connect() as conn:
            # Verificar si la columna ya existe
            check_column = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'call_logs' AND column_name = 'agent_profile_id'
            """))
            column_exists = check_column.fetchone() is not None
            
            if column_exists:
                print("✅ La columna agent_profile_id ya existe en call_logs")
                return
            
            # Verificar si la tabla agent_profiles existe
            check_table = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'agent_profiles'
            """))
            table_exists = check_table.fetchone() is not None
            
            if not table_exists:
                print("⚠️ La tabla agent_profiles no existe. Ejecuta migrate_add_agent_profiles.py primero.")
                return
            
            # Agregar la columna agent_profile_id
            print("📝 Agregando columna agent_profile_id a call_logs...")
            conn.execute(text("""
                ALTER TABLE call_logs 
                ADD COLUMN agent_profile_id INT REFERENCES agent_profiles(id) ON DELETE SET NULL
            """))
            conn.commit()
            print("✅ Columna agent_profile_id agregada")
            
            # Crear índice para mejorar rendimiento
            print("📝 Creando índice en agent_profile_id...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_call_logs_agent_profile_id 
                ON call_logs(agent_profile_id)
            """))
            conn.commit()
            print("✅ Índice creado")
            
            print("✅ Migración completada exitosamente")
            
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    migrate()

