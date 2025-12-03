# init_db.py
from app.persistance.db import Base, engine
# Importar todos los modelos para que SQLAlchemy pueda crear las tablas
from app.models import (
    Company,
    User,
    CompanyPhoneNumber,
    CallLog,
    CallTurn,
    Contact,
    AgentProfile
)

print("🛠️ Creando tablas en PostgreSQL...")
Base.metadata.create_all(bind=engine)
print("✅ Tablas creadas correctamente.")
