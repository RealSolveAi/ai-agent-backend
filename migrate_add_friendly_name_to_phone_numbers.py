#!/usr/bin/env python3
"""
Migración: Agregar columna friendly_name a company_phone_numbers
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL no encontrada en las variables de entorno")
    sys.exit(1)

def parse_database_url(url):
    """Parsea la URL de la base de datos para obtener los parámetros de conexión."""
    # Convertir formato SQLAlchemy a psycopg2 si es necesario
    if url and 'postgresql+psycopg2://' in url:
        url = url.replace('postgresql+psycopg2://', 'postgresql://', 1)
    
    # Formato: postgresql://user:password@host:port/database
    import re
    pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
    match = re.match(pattern, url)
    if match:
        return {
            'user': match.group(1),
            'password': match.group(2),
            'host': match.group(3),
            'port': match.group(4),
            'database': match.group(5)
        }
    return None

def migrate():
    """Agrega la columna friendly_name a company_phone_numbers si no existe."""
    try:
        # Convertir formato SQLAlchemy a psycopg2 si es necesario
        database_url = DATABASE_URL
        if database_url and 'postgresql+psycopg2://' in database_url:
            database_url = database_url.replace('postgresql+psycopg2://', 'postgresql://', 1)
        
        # Parsear la URL de la base de datos
        db_params = parse_database_url(database_url)
        if not db_params:
            print(f"❌ Error: No se pudo parsear DATABASE_URL: {database_url[:50]}...")
            print("   Intentando construir desde variables de entorno...")
            # Intentar construir desde variables de entorno
            db_params = {
                'user': os.getenv('POSTGRES_USER', 'postgres'),
                'password': os.getenv('POSTGRES_PASSWORD', '12345'),
                'host': os.getenv('DB_HOST', 'db'),
                'port': os.getenv('DB_PORT', '5432'),
                'database': os.getenv('POSTGRES_DB', 'realsolveai')
            }
        
        # Conectar a PostgreSQL
        conn = psycopg2.connect(
            host=db_params['host'],
            port=db_params['port'],
            user=db_params['user'],
            password=db_params['password'],
            database=db_params['database']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Verificar si la columna ya existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'company_phone_numbers' 
            AND column_name = 'friendly_name'
        """)
        
        if cursor.fetchone():
            print("✅ La columna 'friendly_name' ya existe en 'company_phone_numbers'")
        else:
            # Agregar la columna
            print("📝 Agregando columna 'friendly_name' a 'company_phone_numbers'...")
            cursor.execute("""
                ALTER TABLE company_phone_numbers 
                ADD COLUMN friendly_name VARCHAR(100)
            """)
            print("✅ Columna 'friendly_name' agregada exitosamente")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error en la migración: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🛠️  Ejecutando migración: agregar friendly_name a company_phone_numbers...")
    if migrate():
        print("✅ Migración completada exitosamente!")
        sys.exit(0)
    else:
        print("❌ Migración falló")
        sys.exit(1)

