from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services import twilio_service
from app.routers.company_router import router as company_router
from app.routers.phone_number_router import router as phone_number_router
from app.routers.call_router import router as call_router
from app.routers.contact_router import router as contact_router
from app.routers.auth_router import router as auth_router
from app.routers.user_router import router as user_router
from app.routers.agent_profile_router import router as agent_profile_router
from app.routers.appointment_router import router as appointment_router
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Realsolve AI Backend", version="1.0")

# Configuración de CORS
# Obtener orígenes permitidos desde variables de entorno o usar valores por defecto
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Permitir todos los orígenes
    allow_credentials=True,  # Permitir cookies y headers de autenticación
    allow_methods=["*"],  # Permitir todos los métodos HTTP (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Permitir todos los headers (incluyendo Authorization para JWT)
)

# Inicializar el scheduler de recordatorios al arrancar la aplicación
@app.on_event("startup")
async def startup_event():
    from app.services.reminder_scheduler import start_scheduler
    start_scheduler()
    print("✅ Servidor iniciado - Scheduler de recordatorios activo")

# Detener el scheduler al cerrar la aplicación
@app.on_event("shutdown")
async def shutdown_event():
    from app.services.reminder_scheduler import stop_scheduler
    stop_scheduler()
    print("❌ Servidor detenido - Scheduler de recordatorios desactivado")

# Principal - modelo assistant AI - SIN CONTROLADOR (ROUTER)
app.include_router(twilio_service.router, tags=["Twilio"])

# Routers
app.include_router(auth_router)
app.include_router(company_router)
app.include_router(phone_number_router)
app.include_router(call_router)
app.include_router(contact_router)
app.include_router(user_router)
app.include_router(agent_profile_router)
app.include_router(appointment_router)

@app.get("/")
async def root():
    return {"message": "RealSolveAI Voice AI Platform is running!"}

