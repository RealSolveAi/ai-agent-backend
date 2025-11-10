import os
import json
import base64
import asyncio
import websockets
from fastapi import APIRouter, WebSocket, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
from app.services.openai_service import initialize_session
from pydantic import BaseModel

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
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created', 'session.updated'
]
SHOW_TIMING_MATH = False

if not OPENAI_API_KEY:
    raise ValueError('Llave de OpenAI API no encontrada. Por favor, establecela en el archivo .env.')

@router.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Servidor de Twilio Media Stream está corriendo!"}

@router.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """ Maneja la llamada entrante y devuelve la respuesta TwiML para conectar a Media Stream."""
    response = VoiceResponse()
    # <Say> punctuation to improve text-to-speech flow
    """ response.say(
        "Por favor, espera mientras conectamos tu llamada al asistente de IA, impulsado por Twilio y la API de Open A I Realtime",
        voice="Google.es-ES-Chirp3-HD-Aoede"
    )
    response.pause(length=1) """
    """ response.say(   
        "O.K. puedes comenzar a hablar!",
        voice="Google.es-ES-Chirp3-HD-Aoede"
    ) """
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

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
    """ Maneja las conexiones WebSocket entre Twilio y OpenAI."""
    print("Cliente conectado")
    await websocket.accept()

    async with websockets.connect(
        f"wss://api.openai.com/v1/realtime?model=gpt-realtime&temperature={TEMPERATURE}",
        additional_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
    ) as openai_ws:
        await initialize_session(openai_ws)

        # Connection specific state
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None
        
        async def receive_from_twilio():
            """Recibe datos de audio de Twilio y los envía a la API de OpenAI Realtime."""
            nonlocal stream_sid, latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'media' and openai_ws.state.name == 'OPEN':
                        latest_media_timestamp = int(data['media']['timestamp'])
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        print(f"Incoming stream has started {stream_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except WebSocketDisconnect:
                print("Cliente desconectado.")
                if openai_ws.state.name == 'OPEN':
                    await openai_ws.close()

        async def send_to_twilio():
            """Recibe eventos de la API de OpenAI Realtime y envía audio de vuelta a Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    if response['type'] in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)

                    if response.get('type') == 'response.output_audio.delta' and 'delta' in response:
                        audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                        audio_delta = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        }
                        await websocket.send_json(audio_delta)


                        if response.get("item_id") and response["item_id"] != last_assistant_item:
                            response_start_timestamp_twilio = latest_media_timestamp
                            last_assistant_item = response["item_id"]
                            if SHOW_TIMING_MATH:
                                print(f"Configurando timestamp para nueva respuesta: {response_start_timestamp_twilio}ms")

                        await send_mark(websocket, stream_sid)

                    # Trigger an interruption. Your use case might work better using `input_audio_buffer.speech_stopped`, or combining the two.
                    if response.get('type') == 'input_audio_buffer.speech_started':
                        print("Se detectó el inicio del habla.")
                        if last_assistant_item:
                            print(f"Interrompiendo respuesta con id: {last_assistant_item}")
                            await handle_speech_started_event()
            except Exception as e:
                print(f"Error en send_to_twilio: {e}")

        async def handle_speech_started_event():
            """ Maneja la interrupción cuando el habla del llamador comienza."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            print("Se detectó el inicio del habla.")
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                if SHOW_TIMING_MATH:
                    print(f"Calculando tiempo transcurrido para truncación: {latest_media_timestamp} - {response_start_timestamp_twilio} = {elapsed_time}ms")

                if last_assistant_item:
                    if SHOW_TIMING_MATH:
                        print(f"Truncando item con ID: {last_assistant_item}, Truncado en: {elapsed_time}ms")

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
            if stream_sid:
                mark_event = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "responsePart"}
                }
                await connection.send_json(mark_event)
                mark_queue.append('responsePart')

        await asyncio.gather(receive_from_twilio(), send_to_twilio())

class PhoneNumberRequest(BaseModel):
    phone_number: str

@router.post("/make-call")
async def make_call(request: PhoneNumberRequest):
    """
    Inicia una llamada saliente al número de teléfono proporcionado.
    """
    try:
        # Obtener la URL base para los webhooks
        phone_number = request.phone_number
        host = os.getenv('HOST')
        if not host.startswith(('http://', 'https://')):
            host = f'https://{host}'
        
        # Crear la respuesta TwiML para la llamada saliente
        response = VoiceResponse()
        """ response.say(
            "Conectando con el asistente de IA, por favor espere.",
            voice="Google.es-ES-Chirp3-HD-Aoede"
        )
        response.pause(length=1) """
        
        # Usar el mismo WebSocket que las llamadas entrantes
        # Extraer solo el dominio sin http/https
        domain = host.split('//')[-1].rstrip('/')
        connect = Connect()
        connect.stream(url=f'wss://{domain}/media-stream')
        response.append(connect)
        
        print(f"Conectando a WebSocket: wss://{domain}/media-stream")
        
        # Realizar la llamada
        call = twilio_client.calls.create(
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))