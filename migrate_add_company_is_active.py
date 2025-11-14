# migrate_add_company_is_active.py
# Script para agregar el campo is_active a la tabla companies
from app.persistance.db import engine
from sqlalchemy import text

def migrate():
    """
    Agrega el campo is_active a la tabla companies si no existe.
    """
    try:
        with engine.connect() as conn:
            # Verificar si la columna ya existe
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='companies' AND column_name='is_active'
            """)
            result = conn.execute(check_query)
            exists = result.fetchone() is not None
            
            if exists:
                print("✅ La columna 'is_active' ya existe en la tabla 'companies'")
                return
            
            # Agregar la columna
            alter_query = text("""
                ALTER TABLE companies 
                ADD COLUMN is_active BOOLEAN DEFAULT TRUE
            """)
            conn.execute(alter_query)
            conn.commit()
            
            print("✅ Columna 'is_active' agregada a la tabla 'companies'")
            print("   Todos los registros existentes se establecieron como activos (is_active = TRUE)")
            
    except Exception as e:
        print(f"❌ Error al migrar: {e}")
        raise

if __name__ == "__main__":
    print("🛠️  Migrando tabla companies...")
    migrate()

