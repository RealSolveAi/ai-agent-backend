# init_db.py
from app.persistance.db import Base, engine
from app.models.company import Company
from app.models.user import User
from app.models.company_phone_number import CompanyPhoneNumber
from app.models.call_log import CallLog
from app.models.call_turn import CallTurn

print("🛠️ Creando tablas en PostgreSQL...")
Base.metadata.create_all(bind=engine)
print("✅ Tablas creadas correctamente.")
