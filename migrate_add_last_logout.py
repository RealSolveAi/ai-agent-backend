# migrate_add_last_logout.py
# Script para agregar el campo last_logout a la tabla users
from app.persistance.db import engine
from sqlalchemy import text

def migrate():
    """
    Agrega el campo last_logout a la tabla users si no existe.
    """
    try:
        with engine.connect() as conn:
            # Verificar si la columna ya existe
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='last_logout'
            """)
            result = conn.execute(check_query)
            exists = result.fetchone() is not None
            
            if exists:
                print("✅ La columna 'last_logout' ya existe en la tabla 'users'")
                return
            
            # Agregar la columna
            alter_query = text("""
                ALTER TABLE users 
                ADD COLUMN last_logout TIMESTAMP WITH TIME ZONE
            """)
            conn.execute(alter_query)
            conn.commit()
            
            print("✅ Columna 'last_logout' agregada a la tabla 'users'")
            
    except Exception as e:
        print(f"❌ Error al migrar: {e}")
        raise

if __name__ == "__main__":
    print("🛠️  Migrando tabla users...")
    migrate()

