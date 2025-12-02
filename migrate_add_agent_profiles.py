"""
Script de migración para crear la tabla agent_profiles.
Ejecutar: python migrate_add_agent_profiles.py
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
    """Crea la tabla agent_profiles si no existe."""
    try:
        with engine.connect() as conn:
            # Verificar si la tabla ya existe
            check_table = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'agent_profiles'
            """))
            table_exists = check_table.fetchone() is not None
            
            if table_exists:
                print("✅ La tabla agent_profiles ya existe")
                # Verificar si tiene la columna updated_at
                check_updated_at = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'agent_profiles' AND column_name = 'updated_at'
                """))
                updated_at_exists = check_updated_at.fetchone() is not None
                
                if not updated_at_exists:
                    print("📝 Agregando columna updated_at a agent_profiles...")
                    conn.execute(text("""
                        ALTER TABLE agent_profiles 
                        ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE
                    """))
                    conn.commit()
                    print("✅ Columna updated_at agregada")
                else:
                    print("✅ La tabla agent_profiles ya tiene todas las columnas necesarias")
                return
            
            # Crear la tabla agent_profiles
            print("📝 Creando tabla agent_profiles...")
            conn.execute(text("""
                CREATE TABLE agent_profiles (
                    id SERIAL PRIMARY KEY,
                    company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    voice VARCHAR(50) DEFAULT 'coral',
                    temperature FLOAT DEFAULT 0.8,
                    prompt TEXT,
                    working_hours JSONB,
                    timezone VARCHAR(50),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE
                )
            """))
            conn.commit()
            print("✅ Tabla agent_profiles creada")
            
            # Crear índice en company_id para mejorar rendimiento
            print("📝 Creando índice en company_id...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_profiles_company_id 
                ON agent_profiles(company_id)
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

