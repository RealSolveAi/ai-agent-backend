from fastapi import FastAPI
from app.services import twilio_service
from app.routers.company_router import router as company_router
from app.routers.phone_number_router import router as phone_number_router
from app.routers.call_router import router as call_router
from app.routers.contact_router import router as contact_router
from app.routers.auth_router import router as auth_router
from app.routers.user_router import router as user_router


app = FastAPI(title="Realsolve AI Backend", version="1.0")

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
