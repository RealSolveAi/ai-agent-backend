#!/bin/bash
set -e

echo "🚀 Iniciando aplicación RealSolveAI..."

# Esperar a que PostgreSQL esté listo
echo "⏳ Esperando a que PostgreSQL esté listo..."
max_attempts=90  # Aumentado a 90 intentos (3 minutos) para la primera inicialización
attempt=0

# Verificar conexión usando Python (más confiable)
until python << 'PYTHON_SCRIPT'
import os
import sys
import psycopg2
from psycopg2 import OperationalError

database_url = os.getenv('DATABASE_URL')
if not database_url:
    # Construir DATABASE_URL desde variables de entorno
    db_user = os.getenv('POSTGRES_USER', 'postgres')
    db_password = os.getenv('POSTGRES_PASSWORD', '12345')
    db_host = os.getenv('DB_HOST', 'db')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('POSTGRES_DB', 'realsolveai')
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    # Si DATABASE_URL tiene formato SQLAlchemy (postgresql+psycopg2://), convertir a formato psycopg2
    # psycopg2.connect() solo acepta postgresql://, no postgresql+psycopg2://
    original_url = database_url
    if 'postgresql+psycopg2://' in database_url:
        database_url = database_url.replace('postgresql+psycopg2://', 'postgresql://')
    # Asegurar que siempre empiece con postgresql://
    if not database_url.startswith('postgresql://'):
        # Si no es una URL válida, construir desde variables de entorno
        db_user = os.getenv('POSTGRES_USER', 'postgres')
        db_password = os.getenv('POSTGRES_PASSWORD', '12345')
        db_host = os.getenv('DB_HOST', 'db')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('POSTGRES_DB', 'realsolveai')
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

try:
    conn = psycopg2.connect(database_url, connect_timeout=2)
    conn.close()
    sys.exit(0)
except OperationalError as e:
    # Errores esperados durante la inicialización
    error_msg = str(e).lower()
    if 'connection refused' in error_msg or 'could not connect' in error_msg or 'server closed the connection' in error_msg:
        sys.exit(1)  # Servidor aún no está listo
    elif 'database' in error_msg and ('does not exist' in error_msg or 'not found' in error_msg):
        # Base de datos no existe aún, pero el servidor está listo
        # Esto es normal en la primera inicialización
        sys.exit(1)
    else:
        # Otro tipo de error, mostrar y salir
        print(f"⚠️  Error de conexión: {e}")
        sys.exit(1)
except Exception as e:
    error_msg = str(e).lower()
    # Si el error es por formato de URL incorrecto, intentar corregirlo
    if 'invalid dsn' in error_msg or 'postgresql+psycopg2' in error_msg:
        # Reconstruir URL desde variables de entorno
        db_user = os.getenv('POSTGRES_USER', 'postgres')
        db_password = os.getenv('POSTGRES_PASSWORD', '12345')
        db_host = os.getenv('DB_HOST', 'db')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('POSTGRES_DB', 'realsolveai')
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        try:
            conn = psycopg2.connect(database_url, connect_timeout=2)
            conn.close()
            sys.exit(0)
        except:
            sys.exit(1)
    else:
        sys.exit(1)
PYTHON_SCRIPT
do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ Error: PostgreSQL no está disponible después de $max_attempts intentos (~3 minutos)"
        echo "   Verificando estado de PostgreSQL..."
        echo "   DATABASE_URL: ${DATABASE_URL:-'no definida'}"
        # Mostrar el error real
        python << 'PYTHON_SCRIPT'
import os
import psycopg2
database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:12345@db:5432/realsolveai')
# Convertir formato SQLAlchemy a psycopg2 si es necesario
if database_url.startswith('postgresql+psycopg2://'):
    database_url = database_url.replace('postgresql+psycopg2://', 'postgresql://', 1)
try:
    conn = psycopg2.connect(database_url, connect_timeout=5)
    conn.close()
    print("✅ ¡La conexión funciona ahora!")
except Exception as e:
    print(f"❌ Error de conexión: {e}")
PYTHON_SCRIPT
        exit 1
    fi
    if [ $((attempt % 10)) -eq 0 ]; then
        echo "⏳ PostgreSQL no está listo aún... (intento $attempt/$max_attempts - espera hasta 3 minutos en primera inicialización)"
    fi
    sleep 2
done

echo "✅ PostgreSQL está listo!"

# Inicializar base de datos desde SQL y crear superadmin
echo "🛠️ Inicializando base de datos..."
if [ -f "realsolve_ai_bd.sql" ]; then
    echo "📄 Ejecutando script SQL completo..."
    if python init_database.py; then
        echo "✅ Base de datos inicializada desde SQL"
    else
        echo "⚠️ Advertencia: Error al ejecutar SQL, intentando con init_db.py..."
        python init_db.py || echo "⚠️ Error también en init_db.py"
    fi
else
    echo "📄 Archivo SQL no encontrado, usando init_db.py..."
    if python init_db.py; then
        echo "✅ Tablas creadas/verificadas correctamente"
    else
        echo "⚠️ Advertencia: Error al inicializar tablas (puede que ya existan)"
    fi
fi

# Las migraciones ya están incluidas en realsolve_ai_bd.sql
# Solo ejecutar migraciones si NO usamos el SQL completo (para actualizaciones futuras)
if [ ! -f "realsolve_ai_bd.sql" ]; then
    echo "🔄 Ejecutando migraciones (solo si no se usó SQL completo)..."
    for migration in migrate_add_call_statuses.py migrate_add_company_is_active.py migrate_add_last_logout.py migrate_add_recording_fields.py migrate_add_agent_profiles.py migrate_add_agent_profile_id_to_call_logs.py; do
        if [ -f "$migration" ]; then
            echo "  → Ejecutando $migration..."
            python "$migration" || echo "  ⚠️ Advertencia: $migration falló (puede que ya esté aplicada)"
        fi
    done
else
    echo "ℹ️  Migraciones incluidas en SQL, saltando migraciones separadas"
fi

echo "✅ Base de datos inicializada!"

# Ejecutar el comando principal
echo "🚀 Iniciando servidor..."
exec "$@"
