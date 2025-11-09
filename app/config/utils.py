import jwt, datetime, hashlib, base64, os
from pydub import AudioSegment
import io

SECRET_KEY = os.getenv("JWT_SECRET", "supersecret")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_jwt(email: str):
    payload = {"sub": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def convert_to_pcmu(audio_bytes: bytes) -> bytes:
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    pcmu_audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(1)
    out_io = io.BytesIO()
    pcmu_audio.export(out_io, format="wav", codec="pcm_mulaw")
    return out_io.getvalue()
