from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.persistance.db import SessionLocal
from app.models.call_log import CallLog
from app.models.user import User
from app.config.security import decode_access_token

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str, db: Session):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user

class CallLogCreate(BaseModel):
    call_sid: str
    duration: float
    transcript: str

@router.post("/log")
def save_call(call: CallLogCreate, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    new_call = CallLog(
        user_id=user.id,
        call_sid=call.call_sid,
        duration=call.duration,
        transcript=call.transcript
    )
    db.add(new_call)
    db.commit()
    db.refresh(new_call)
    return {"message": "Llamada registrada", "id": new_call.id}

@router.get("/history")
def get_call_history(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    calls = db.query(CallLog).filter(CallLog.user_id == user.id).all()
    return calls
