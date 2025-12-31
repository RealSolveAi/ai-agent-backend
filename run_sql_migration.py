"""
Script Python para ejecutar la migración SQL de appointments.
Ejecutar: python run_sql_migration.py
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    """Ejecuta el script SQL de migración."""
    
    print("🔄 Iniciando migración de appointments...")
    
    try:
        # Obtener URL de la base de datos
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL no está configurada en el archivo .env")
        
        # Convertir de formato SQLAlchemy a psycopg2
        # De: postgresql+psycopg2://user:pass@host:port/db
        # A: postgresql://user:pass@host:port/db
        if database_url.startswith("postgresql+psycopg2://"):
            database_url = database_url.replace("postgresql+psycopg2://", "postgresql://")
        
        print(f"📊 Conectando a la base de datos...")
        
        # Conectar a PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Leer el archivo SQL
        with open('migrate_appointments.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Ejecutar el script
        print("✨ Ejecutando script SQL...")
        cursor.execute(sql_script)
        conn.commit()
        
        print("✅ Migración completada exitosamente!")
        print("📋 Tablas creadas:")
        print("   - appointments")
        print("   - appointment_reminders")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error durante la migración: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migration()
