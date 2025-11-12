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
from app.services.save_call_to_db import (
    create_call_log_from_phone_number,
    add_turn,
    finish_call
)
from app.persistance.db import SessionLocal
from app.models.call_log import CallLog
from app.models.call_turn import Speaker
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
    # Obtener parámetros de la llamada de Twilio
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    from_number = form_data.get("From")  # Número que llama
    to_number = form_data.get("To")  # Número que recibe (nuestro número de Twilio)
    
    print(f"📞 Llamada entrante - CallSid: {call_sid}, From: {from_number}, To: {to_number}")
    
    # Crear CallLog en la base de datos
    if call_sid and to_number:
        call_log_id = create_call_log_from_phone_number(
            phone_number_str=to_number,
            call_sid=call_sid,
            direction="inbound",
            from_number=from_number
        )
        if call_log_id:
            print(f"✅ CallLog creado para llamada entrante: {call_log_id}")
        else:
            print(f"⚠️ No se pudo crear CallLog para la llamada entrante")
    
    response = VoiceResponse()
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream?call_sid={call_sid}')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """ Maneja las conexiones WebSocket entre Twilio y OpenAI."""
    print("Cliente conectado")
    await websocket.accept()
    
    # Obtener call_sid de los query parameters
    call_sid = websocket.query_params.get("call_sid")
    call_log_id = None
    
    # Buscar CallLog por call_sid si está disponible
    if call_sid:
        db = SessionLocal()
        try:
            call_log = db.query(CallLog).filter(CallLog.call_sid == call_sid).first()
            if call_log:
                call_log_id = call_log.id
                print(f"✅ CallLog encontrado: ID={call_log_id}, CallSid={call_sid}")
            else:
                print(f"⚠️ No se encontró CallLog para CallSid: {call_sid}")
        except Exception as e:
            print(f"❌ Error al buscar CallLog: {e}")
        finally:
            db.close()

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
        current_user_transcription = ""  # Para acumular transcripciones del usuario
        current_assistant_content = ""  # Para acumular contenido del asistente
        
        async def receive_from_twilio():
            """Recibe datos de audio de Twilio y los envía a la API de OpenAI Realtime."""
            nonlocal stream_sid, latest_media_timestamp, call_sid, call_log_id
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
                        # Obtener call_sid del evento start si no lo tenemos
                        if not call_sid:
                            call_sid = data['start'].get('callSid')
                            if call_sid and not call_log_id:
                                # Buscar CallLog por call_sid
                                db = SessionLocal()
                                try:
                                    call_log = db.query(CallLog).filter(CallLog.call_sid == call_sid).first()
                                    if call_log:
                                        call_log_id = call_log.id
                                        print(f"✅ CallLog encontrado desde evento start: ID={call_log_id}, CallSid={call_sid}")
                                except Exception as e:
                                    print(f"❌ Error al buscar CallLog desde evento start: {e}")
                                finally:
                                    db.close()
                        print(f"Incoming stream has started {stream_sid}, CallSid: {call_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except WebSocketDisconnect:
                print("Cliente desconectado.")
                # Finalizar la llamada en la base de datos
                if call_log_id:
                    try:
                        # Calcular duración si tenemos start_time
                        db = SessionLocal()
                        try:
                            call_log = db.query(CallLog).filter(CallLog.id == call_log_id).first()
                            if call_log and call_log.start_time:
                                from datetime import datetime, timezone
                                duration = int((datetime.now(timezone.utc) - call_log.start_time).total_seconds())
                                finish_call(call_log_id, duration_seconds=duration)
                                print(f"✅ Llamada finalizada: ID={call_log_id}, Duración={duration}s")
                            else:
                                finish_call(call_log_id)
                        finally:
                            db.close()
                    except Exception as e:
                        print(f"❌ Error al finalizar llamada: {e}")
                if openai_ws.state.name == 'OPEN':
                    await openai_ws.close()

        async def send_to_twilio():
            """Recibe eventos de la API de OpenAI Realtime y envía audio de vuelta a Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, current_user_transcription, current_assistant_content
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    if response['type'] in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)

                    # Capturar transcripción del usuario
                    # Evento cuando se completa la transcripción del audio del usuario
                    if response.get('type') == 'conversation.item.input_audio_transcription.completed':
                        transcription = response.get('transcript', '')
                        if transcription and call_log_id:
                            print(f"🎤 Usuario dijo: {transcription}")
                            try:
                                add_turn(call_log_id, Speaker.user, transcription)
                                print(f"✅ Turno del usuario guardado")
                            except Exception as e:
                                print(f"❌ Error al guardar turno del usuario: {e}")
                    
                    # Capturar transcripción del usuario desde conversation.item.created
                    if response.get('type') == 'conversation.item.created':
                        item = response.get('item', {})
                        if item.get('type') == 'message' and item.get('role') == 'user':
                            # Buscar transcripción en el contenido
                            content = item.get('content', [])
                            for part in content:
                                if part.get('type') == 'input_audio' and 'transcript' in part:
                                    transcription = part.get('transcript', '')
                                    if transcription and call_log_id:
                                        print(f"🎤 Usuario dijo (desde item.created): {transcription}")
                                        try:
                                            add_turn(call_log_id, Speaker.user, transcription)
                                        except Exception as e:
                                            print(f"❌ Error al guardar turno del usuario: {e}")
                    
                    # Capturar contenido del asistente desde response.done
                    # Este es el evento principal donde viene el transcript del asistente
                    if response.get('type') == 'response.done':
                        response_data = response.get('response', {})
                        output = response_data.get('output', [])
                        
                        for item in output:
                            if item.get('type') == 'message' and item.get('role') == 'assistant':
                                content = item.get('content', [])
                                transcript_text = ""
                                
                                # Buscar transcript en output_audio
                                for part in content:
                                    if part.get('type') == 'output_audio' and 'transcript' in part:
                                        transcript_text = part.get('transcript', '')
                                        break
                                
                                # Si no hay transcript en output_audio, buscar en text
                                if not transcript_text:
                                    for part in content:
                                        if part.get('type') == 'text':
                                            transcript_text += part.get('text', '')
                                
                                if transcript_text and call_log_id:
                                    print(f"🤖 Asistente dijo: {transcript_text}")
                                    try:
                                        add_turn(call_log_id, Speaker.assistant, transcript_text)
                                        print(f"✅ Turno del asistente guardado")
                                    except Exception as e:
                                        print(f"❌ Error al guardar turno del asistente: {e}")
                    
                    # Capturar contenido del asistente desde response.content.done (alternativa)
                    if response.get('type') == 'response.content.done':
                        item = response.get('item', {})
                        if item.get('type') == 'message' and item.get('role') == 'assistant':
                            content = item.get('content', [])
                            text_content = ""
                            for part in content:
                                if part.get('type') == 'output_audio' and 'transcript' in part:
                                    text_content = part.get('transcript', '')
                                    break
                                elif part.get('type') == 'text':
                                    text_content += part.get('text', '')
                            
                            if text_content and call_log_id:
                                print(f"🤖 Asistente dijo (desde content.done): {text_content}")
                                try:
                                    add_turn(call_log_id, Speaker.assistant, text_content)
                                except Exception as e:
                                    print(f"❌ Error al guardar turno del asistente: {e}")

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
                # Finalizar llamada en caso de error
                if call_log_id:
                    try:
                        finish_call(call_log_id)
                    except:
                        pass

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
        
        print(f"📞 Llamada saliente iniciada - CallSid: {call.sid}, To: {phone_number}, From: {TWILIO_PHONE_NUMBER}")
        
        # Crear CallLog en la base de datos
        if call.sid:
            call_log_id = create_call_log_from_phone_number(
                phone_number_str=TWILIO_PHONE_NUMBER,
                call_sid=call.sid,
                direction="outbound",
                from_number=phone_number
            )
            if call_log_id:
                print(f"✅ CallLog creado para llamada saliente: {call_log_id}")
            else:
                print(f"⚠️ No se pudo crear CallLog para la llamada saliente")
        
        return {
            "status": "Llamada iniciada",
            "call_sid": call.sid,
            "to": phone_number,
            "from": TWILIO_PHONE_NUMBER,
            "twiml": str(response)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))