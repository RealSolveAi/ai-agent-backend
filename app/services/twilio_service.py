import os
import json
import base64
import asyncio
import websockets
from fastapi import APIRouter, WebSocket, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
from app.services.openai_service import initialize_session

load_dotenv()
router = APIRouter()

# --- Variables de entorno ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.8))
HOST = os.getenv("HOST")

# --- Cliente Twilio ---
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

LOG_EVENT_TYPES = [
    "error", "response.content.done", "rate_limits.updated",
    "response.done", "input_audio_buffer.committed",
    "input_audio_buffer.speech_stopped", "input_audio_buffer.speech_started",
    "session.created", "session.updated"
]
SHOW_TIMING_MATH = False


@router.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Maneja llamadas entrantes y devuelve la TwiML."""
    host = request.url.hostname
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Maneja el flujo de audio entre Twilio y OpenAI."""
    print("Cliente conectado desde Twilio")
    await websocket.accept()

    async with websockets.connect(
        f"wss://api.openai.com/v1/realtime?model=gpt-realtime-mini&temperature={TEMPERATURE}",
        additional_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
    ) as openai_ws:
        await initialize_session(openai_ws, TEMPERATURE)

        # Variables locales
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None

        async def receive_from_twilio():
            """Recibe audio de Twilio → envía a OpenAI."""
            nonlocal stream_sid, latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data["event"] == "media" and openai_ws.state.name == "OPEN":
                        latest_media_timestamp = int(data["media"]["timestamp"])
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"]
                        }))
                    elif data["event"] == "start":
                        stream_sid = data["start"]["streamSid"]
                        print(f"🟢 Stream iniciado {stream_sid}")
                    elif data["event"] == "mark" and mark_queue:
                        mark_queue.pop(0)
            except WebSocketDisconnect:
                print("Cliente desconectado.")
                if openai_ws.state.name == "OPEN":
                    await openai_ws.close()

        async def send_to_twilio():
            """Envía el audio generado por OpenAI → Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)

                    if response["type"] in LOG_EVENT_TYPES:
                        print(f"Evento recibido: {response['type']}")

                    if response.get("type") == "response.output_audio.delta" and "delta" in response:
                        audio_payload = base64.b64encode(base64.b64decode(response["delta"])).decode("utf-8")
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": audio_payload}
                        })

                        if response.get("item_id") and response["item_id"] != last_assistant_item:
                            response_start_timestamp_twilio = latest_media_timestamp
                            last_assistant_item = response["item_id"]

                            if SHOW_TIMING_MATH:
                                print(f"Nuevo timestamp: {response_start_timestamp_twilio} ms")

                        await send_mark(websocket, stream_sid)

                    if response.get("type") == "input_audio_buffer.speech_started":
                        print("🎙️ Se detectó inicio del habla.")
                        if last_assistant_item:
                            await handle_speech_started_event()
            except Exception as e:
                print(f"❌ Error en send_to_twilio: {e}")

        async def handle_speech_started_event():
            """Interrumpe la IA cuando el usuario comienza a hablar."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            print("🛑 Interrupción de IA detectada.")
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                if SHOW_TIMING_MATH:
                    print(f"Duración truncada: {elapsed_time} ms")

                if last_assistant_item:
                    truncate_event = {
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time
                    }
                    await openai_ws.send(json.dumps(truncate_event))

                await websocket.send_json({
                    "event": "clear",
                    "streamSid": stream_sid
                })

                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

        async def send_mark(connection, stream_sid):
            """Envía marcas de progreso al cliente Twilio."""
            mark_event = {
                "event": "mark",
                "streamSid": stream_sid,
                "mark": {"name": "responsePart"}
            }
            await connection.send_json(mark_event)
            mark_queue.append("responsePart")

        await asyncio.gather(receive_from_twilio(), send_to_twilio())


@router.post("/make-call")
async def make_call(data: dict):
    """Inicia una llamada saliente."""
    phone_number = data.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="Falta el número de destino.")

    host = os.getenv("HOST")
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"

    domain = host.split("//")[-1].rstrip("/")
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{domain}/media-stream")
    response.append(connect)

    print(f"Conectando a WebSocket: wss://{domain}/media-stream")
    call = client.calls.create(
        twiml=str(response),
        to=phone_number,
        from_=TWILIO_PHONE_NUMBER
    )

    return {
        "status": "Llamada iniciada",
        "call_sid": call.sid,
        "to": phone_number,
        "from": TWILIO_PHONE_NUMBER,
        "twiml": str(response)
    }
