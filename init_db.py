from app.persistance.db import Base, engine
from app.models.user import User
from app.models.call_log import CallLog

print("Creando tablas en PostgreSQL...")
Base.metadata.create_all(bind=engine)
print("Tablas creadas correctamente.")
