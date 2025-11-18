from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services import twilio_service
from app.routers.company_router import router as company_router
from app.routers.phone_number_router import router as phone_number_router
from app.routers.call_router import router as call_router
from app.routers.contact_router import router as contact_router
from app.routers.auth_router import router as auth_router
from app.routers.user_router import router as user_router
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Realsolve AI Backend", version="1.0")

# Configuración de CORS
# Obtener orígenes permitidos desde variables de entorno o usar valores por defecto
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:5173"
).split(",")

# Limpiar espacios en blanco
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos los orígenes
    allow_credentials=True,  # Permitir cookies y headers de autenticación
    allow_methods=["*"],  # Permitir todos los métodos HTTP (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Permitir todos los headers (incluyendo Authorization para JWT)
)

# Principal - modelo assistant AI - SIN CONTROLADOR (ROUTER)
app.include_router(twilio_service.router, tags=["Twilio"])

# Routers
app.include_router(auth_router)
app.include_router(company_router)
app.include_router(phone_number_router)
app.include_router(call_router)
app.include_router(contact_router)
app.include_router(user_router)

@app.get("/")
async def root():
    return {"message": "RealSolveAI Voice AI Platform is running!"}
