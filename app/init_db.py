from app.db import Base, engine
from app.models.call_log import CallLog

print("Creando tablas en postgres...")
Base.metadata.create_all(engine)
print("Tablas creadas")