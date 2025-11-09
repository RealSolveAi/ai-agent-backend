from fastapi import FastAPI
from app.api import users, calls
from app.services import twilio_service

app = FastAPI(title="Voice AI Platform", version="1.0")

# Rutas REST principales
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(calls.router, prefix="/api/calls", tags=["Calls"])

# Webhooks de Twilio (no se autentican con JWT)
app.include_router(twilio_service.router, tags=["Twilio"])

@app.get("/")
async def root():
    return {"message": "Plataforma Voice AI activa y corriendo!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=5050, reload=True)
