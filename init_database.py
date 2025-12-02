#!/usr/bin/env python3
"""
Script para inicializar la base de datos desde el archivo SQL
y crear el usuario superadmin.
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import re

# Cargar variables de entorno
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

def execute_sql_file(sql_file_path):
    """Ejecuta un archivo SQL completo usando psycopg2."""
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
            print(f"   Usando: postgresql://{db_params['user']}:***@{db_params['host']}:{db_params['port']}/{db_params['database']}")
        
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
        
        # Leer el archivo SQL
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Dividir en sentencias (separadas por ;)
        # Remover comentarios de línea (--)
        statements = []
        current_statement = []
        
        for line in sql_content.split('\n'):
            line = line.strip()
            # Saltar líneas vacías y comentarios
            if not line or line.startswith('--'):
                continue
            
            # Remover comentarios al final de la línea
            if '--' in line:
                line = line.split('--')[0].strip()
            
            current_statement.append(line)
            
            # Si la línea termina con ';', es el final de una sentencia
            if line.endswith(';'):
                statement = ' '.join(current_statement)
                if statement and statement != ';':
                    statements.append(statement)
                current_statement = []
        
        # Ejecutar cada sentencia
        executed = 0
        skipped = 0
        errors = 0
        
        for i, statement in enumerate(statements, 1):
            try:
                statement = statement.rstrip(';').strip()
                if not statement:
                    continue
                
                cursor.execute(statement)
                executed += 1
                if executed % 10 == 0:
                    print(f"  📝 Ejecutadas {executed} sentencias...")
                    
            except psycopg2.errors.DuplicateObject as e:
                # Objeto ya existe (enum, tabla, etc.) - esto es normal
                skipped += 1
            except psycopg2.errors.DuplicateTable as e:
                # Tabla ya existe - esto es normal
                skipped += 1
            except Exception as e:
                error_msg = str(e)
                # Algunos errores son esperados
                if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                    skipped += 1
                else:
                    errors += 1
                    print(f"  ⚠️  Error en sentencia {i}: {error_msg[:150]}")
        
        cursor.close()
        conn.close()
        
        print(f"✅ SQL ejecutado: {executed} sentencias ejecutadas, {skipped} omitidas (ya existían), {errors} errores")
        return True
        
    except FileNotFoundError:
        print(f"⚠️  Archivo SQL no encontrado: {sql_file_path}")
        return False
    except Exception as e:
        print(f"❌ Error al ejecutar archivo SQL: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_user_role_enum(engine):
    """Agrega 'superadmin' al enum user_role si no existe."""
    try:
        with engine.connect() as conn:
            # Verificar si 'superadmin' ya existe en el enum
            check_query = text("""
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'superadmin' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_role')
            """)
            result = conn.execute(check_query)
            exists = result.fetchone() is not None
            
            if not exists:
                print("📝 Agregando 'superadmin' al enum user_role...")
                # Nota: ALTER TYPE ... ADD VALUE no puede ejecutarse en una transacción
                # Por eso usamos execute directamente sin commit explícito
                conn.execute(text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'superadmin'"))
                conn.commit()
                print("✅ 'superadmin' agregado al enum user_role")
            else:
                print("✅ 'superadmin' ya existe en el enum user_role")
        
        return True
    except Exception as e:
        print(f"⚠️  Advertencia al actualizar enum user_role: {e}")
        # Continuar de todas formas
        return True

def main():
    print("🛠️  Inicializando base de datos desde SQL...")
    
    # Convertir formato SQLAlchemy a psycopg2 si es necesario
    database_url = DATABASE_URL
    if database_url and 'postgresql+psycopg2://' in database_url:
        database_url = database_url.replace('postgresql+psycopg2://', 'postgresql://', 1)
    
    engine = create_engine(database_url)
    
    # Ejecutar el archivo SQL
    sql_file = "realsolve_ai_bd.sql"
    sql_executed = False
    if os.path.exists(sql_file):
        print(f"📄 Ejecutando {sql_file}...")
        sql_executed = execute_sql_file(sql_file)
    else:
        print(f"⚠️  Archivo {sql_file} no encontrado, saltando inicialización SQL")
    
    # Actualizar el enum user_role para incluir 'superadmin' solo si el SQL se ejecutó
    # (el enum ya debería tener 'superadmin' si el SQL se ejecutó correctamente)
    if sql_executed:
        print("🔄 Verificando enum user_role...")
        update_user_role_enum(engine)
    else:
        print("⚠️  Saltando actualización de enum (SQL no se ejecutó correctamente)")
    
    # Crear el superadmin
    print("👤 Creando usuario superadmin...")
    try:
        from create_superadmin import create_superadmin
        create_superadmin()
    except Exception as e:
        print(f"❌ Error al crear superadmin: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("✅ Base de datos inicializada completamente!")

if __name__ == "__main__":
    main()

