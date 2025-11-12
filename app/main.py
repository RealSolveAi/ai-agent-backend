from fastapi import FastAPI
from app.api import users, calls
from app.services import twilio_service
from app.routers.company_router import router as company_router
from app.routers.phone_number_router import router as phone_number_router
from app.routers.call_router import router as call_router


app = FastAPI(title="Realsolve AI Backend", version="1.0")

app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(calls.router, prefix="/api/calls", tags=["Calls"])
app.include_router(twilio_service.router, tags=["Twilio"])

# Routers
app.include_router(company_router)
app.include_router(phone_number_router)
app.include_router(call_router)

@app.get("/")
async def root():
    return {"message": "RealSolveAI Voice AI Platform is running!"}
