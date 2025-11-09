from datetime import datetime
from sqlalchemy.orm import Session
from app.persistance.db import SessionLocal
from app.models.call_log import CallLog
from app.models.user import User

def save_call_to_db(user_email: str, call_sid: str, transcript: str, duration: float):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            print(f"Usuario no encontrado para email: {user_email}")
            return

        new_call = CallLog(
            user_id=user.id,
            call_sid=call_sid,
            duration=duration,
            transcript=transcript,
            created_at=datetime.now(datetime.timezone.utc)
        )
        db.add(new_call)
        db.commit()
        print(f"Llamada registrada automáticamente: {call_sid}")
    finally:
        db.close()
