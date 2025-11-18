import os
import json
import base64
import asyncio
import websockets
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
from app.services.openai_service import initialize_session
from app.services.save_call_to_db import (
    create_call_log_from_phone_number,
    add_turn,
    finish_call,
    update_call_recording_url
)
from app.persistance.db import SessionLocal
from app.models.call_log import CallLog
from app.models.call_turn import Speaker
from app.models.user import User
from app.routers.auth_router import get_current_user
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


# IMPORTANTE: Este endpoint debe ser PÚBLICO (sin autenticación)
# Es un webhook de Twilio que recibe el status callback de las llamadas
# Incluye el recording_url cuando la grabación está disponible
@router.api_route("/call-status", methods=["GET", "POST"])
async def handle_call_status(request: Request):
    """
    Maneja el status callback de Twilio para actualizar el estado de la llamada
    y guardar el recording_url cuando esté disponible.
    
    Este endpoint es público y no requiere autenticación ya que es llamado por Twilio
    como webhook cuando cambia el estado de una llamada o cuando la grabación está lista.
    """
    try:
        # Obtener parámetros del webhook de Twilio
        # Twilio envía los datos como form-data (application/x-www-form-urlencoded)
        try:
            form_data = await request.form()
        except Exception as form_error:
            # Si falla el form parsing, intentar obtener de query params o body
            print(f"⚠️ Error al parsear form, intentando alternativas: {form_error}")
            # Intentar desde query params
            if request.method == "GET":
                form_data = request.query_params
            else:
                # Intentar parsear el body manualmente
                body = await request.body()
                if body:
                    from urllib.parse import parse_qs
                    parsed = parse_qs(body.decode())
                    form_data = {k: v[0] if v else None for k, v in parsed.items()}
                else:
                    form_data = {}
        
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        recording_sid = form_data.get("RecordingSid")
        recording_url = form_data.get("RecordingUrl")
        recording_status = form_data.get("RecordingStatus")
        recording_duration = form_data.get("RecordingDuration")
        
        print(f"📞 Status callback - CallSid: {call_sid}, Status: {call_status}, RecordingStatus: {recording_status}, RecordingSid: {recording_sid}")
        print(f"📋 Todos los parámetros recibidos: {dict(form_data) if hasattr(form_data, 'keys') else form_data}")
        
        # Si hay recording_sid o recording_url, actualizar el CallLog
        if call_sid and (recording_sid or recording_url):
            # Construir URL completa del recording
            if recording_sid:
                # Si tenemos RecordingSid, construir la URL completa
                final_recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Recordings/{recording_sid}"
            elif recording_url:
                # Si ya viene la URL completa, usarla
                final_recording_url = recording_url
            else:
                final_recording_url = None
            
            # Parsear recording_duration si está disponible
            recording_duration_int = None
            if recording_duration:
                try:
                    recording_duration_int = int(recording_duration)
                except (ValueError, TypeError):
                    pass
            
            if final_recording_url:
                try:
                    success = update_call_recording_url(
                        call_sid, 
                        final_recording_url,
                        recording_sid=recording_sid,
                        recording_duration=recording_duration_int
                    )
                    if success:
                        print(f"✅ Recording URL guardado para CallSid: {call_sid}, URL: {final_recording_url}, SID: {recording_sid}, Duration: {recording_duration_int}s")
                    else:
                        print(f"⚠️ No se pudo guardar Recording URL para CallSid: {call_sid}")
                except Exception as e:
                    print(f"⚠️ Error al guardar Recording URL (no crítico): {e}")
        
        # Si la llamada está completada y no tenemos recording_url, intentar obtenerlo de la API de Twilio
        if call_sid and call_status == "completed" and not recording_sid and not recording_url:
            try:
                # Obtener la llamada de Twilio para ver si tiene grabaciones
                call = twilio_client.calls(call_sid).fetch()
                if call:
                    # Buscar grabaciones asociadas a esta llamada
                    recordings = twilio_client.recordings.list(call_sid=call_sid, limit=1)
                    if recordings:
                        recording = recordings[0]
                        recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Recordings/{recording.sid}"
                        recording_duration_int = None
                        if hasattr(recording, 'duration') and recording.duration:
                            try:
                                recording_duration_int = int(recording.duration)
                            except (ValueError, TypeError):
                                pass
                        success = update_call_recording_url(
                            call_sid, 
                            recording_url,
                            recording_sid=recording.sid,
                            recording_duration=recording_duration_int
                        )
                        if success:
                            print(f"✅ Recording URL obtenido de API y guardado para CallSid: {call_sid}, URL: {recording_url}, SID: {recording.sid}, Duration: {recording_duration_int}s")
            except Exception as e:
                print(f"⚠️ Error al obtener recording de API (no crítico): {e}")
        
        # Actualizar estado de la llamada si es necesario
        # NOTA: No marcamos como completed aquí, solo cuando tengamos recording_duration
        if call_sid and call_status:
            db = SessionLocal()
            try:
                call_log = db.query(CallLog).filter(CallLog.call_sid == call_sid).first()
                if call_log:
                    from app.models.call_log import CallStatus
                    # Mapear estados de Twilio a nuestros estados
                    # NO marcamos como completed aquí, solo cuando tengamos recording_duration
                    status_mapping = {
                        "queued": CallStatus.in_progress,
                        "ringing": CallStatus.in_progress,
                        "in-progress": CallStatus.in_progress,
                        # "completed": NO lo marcamos aquí, se marca cuando tengamos recording_duration
                        "busy": CallStatus.failed,
                        "failed": CallStatus.failed,
                        "no-answer": CallStatus.no_answer,  # No contestaron la llamada
                        "canceled": CallStatus.failed
                    }
                    if call_status in status_mapping:
                        # Solo actualizar si no es "completed" (completed se maneja cuando tengamos recording_duration)
                        if call_status != "completed":
                            call_log.status = status_mapping[call_status]
                        # Si es "completed" pero aún no tenemos recording_duration, solo actualizar end_time
                        elif call_status == "completed" and not call_log.recording_duration:
                            call_log.end_time = datetime.now(timezone.utc)
                            # No marcamos como completed hasta tener recording_duration
                        db.commit()
                        print(f"✅ Estado de llamada actualizado: {call_status} (completed se marcará cuando tengamos recording_duration)")
            except Exception as e:
                db.rollback()
                print(f"⚠️ Error al actualizar estado (no crítico): {e}")
            finally:
                db.close()
        
        # Retornar respuesta vacía (Twilio espera 200 OK)
        return HTMLResponse(content="", status_code=200)
        
    except Exception as e:
        print(f"❌ Error en handle_call_status: {e}")
        import traceback
        traceback.print_exc()
        # Retornar 200 para que Twilio no reintente
        return HTMLResponse(content="", status_code=200)

# IMPORTANTE: Este endpoint debe ser PÚBLICO (sin autenticación)
# Es un webhook de Twilio que recibe llamadas entrantes
# No debe tener dependencias de autenticación (get_current_user, etc.)
@router.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """
    Maneja la llamada entrante y devuelve la respuesta TwiML para conectar a Media Stream.
    
    Este endpoint es público y no requiere autenticación ya que es llamado por Twilio
    como webhook cuando se recibe una llamada entrante.
    """
    try:
        # Obtener parámetros de la llamada de Twilio
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")  # Número que llama
        to_number = form_data.get("To")  # Número que recibe (nuestro número de Twilio)
        
        print(f"📞 Llamada entrante - CallSid: {call_sid}, From: {from_number}, To: {to_number}")
        
        # Habilitar grabación para llamadas entrantes
        if call_sid:
            try:
                host = HOST if HOST else request.url.hostname
                if host and host.startswith(('http://', 'https://')):
                    host = host.split('//')[-1].rstrip('/')
                elif not host:
                    host = request.url.hostname
                
                # Actualizar la llamada para habilitar grabación
                twilio_client.calls(call_sid).update(
                    record=True,
                    recording_status_callback=f'https://{host}/call-status',
                    recording_status_callback_method='POST'
                )
                print(f"✅ Grabación habilitada para llamada entrante: {call_sid}")
            except Exception as e:
                print(f"⚠️ Error al habilitar grabación (no crítico): {e}")
        
        # Crear CallLog en la base de datos (no crítico si falla)
        if call_sid and to_number:
            try:
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
            except Exception as e:
                # No fallar la llamada si no se puede crear el CallLog
                print(f"⚠️ Error al crear CallLog (no crítico): {e}")
        
        # Construir respuesta TwiML
        response = VoiceResponse()
        
        # Obtener el hostname correcto para el WebSocket
        # Intentar usar HOST de variables de entorno, si no usar el hostname de la request
        host = HOST if HOST else request.url.hostname
        
        # Limpiar el host (remover http:// o https:// si están presentes)
        if host and host.startswith(('http://', 'https://')):
            host = host.split('//')[-1].rstrip('/')
        elif not host:
            host = request.url.hostname
        
        # Construir URL del WebSocket
        ws_url = f'wss://{host}/media-stream'
        if call_sid:
            ws_url += f'?call_sid={call_sid}'
        
        print(f"🔗 Conectando a WebSocket: {ws_url}")
        
        connect = Connect()
        connect.stream(url=ws_url)
        response.append(connect)
        
        # Nota: La grabación se habilita a nivel de llamada, no en TwiML cuando usamos Media Stream
        # El recording_url se recibirá en el webhook /call-status
        
        twiml_response = str(response)
        print(f"📋 TwiML generado: {twiml_response}")
        
        return HTMLResponse(content=twiml_response, media_type="application/xml")
        
    except Exception as e:
        # En caso de error, intentar devolver una respuesta básica para que la llamada no se cuelgue
        print(f"❌ Error crítico en handle_incoming_call: {e}")
        traceback.print_exc()
        
        try:
            # Intentar devolver una respuesta básica
            response = VoiceResponse()
            host = HOST if HOST else request.url.hostname
            if host and host.startswith(('http://', 'https://')):
                host = host.split('//')[-1].rstrip('/')
            elif not host:
                host = request.url.hostname or "localhost"
            
            ws_url = f'wss://{host}/media-stream'
            connect = Connect()
            connect.stream(url=ws_url)
            response.append(connect)
            return HTMLResponse(content=str(response), media_type="application/xml")
        except Exception as fallback_error:
            # Si incluso el fallback falla, devolver error pero con status 200 para que Twilio no cuelgue
            print(f"❌ Error en fallback: {fallback_error}")
            error_response = VoiceResponse()
            error_response.say("Sorry, there was an error connecting the call. Please try again later.")
            return HTMLResponse(content=str(error_response), media_type="application/xml")


# IMPORTANTE: Este WebSocket debe ser PÚBLICO (sin autenticación)
# Es usado por Twilio para transmitir audio en tiempo real
# No debe tener dependencias de autenticación
@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """
    Maneja las conexiones WebSocket entre Twilio y OpenAI.
    
    Este WebSocket es público y no requiere autenticación ya que es usado por Twilio
    para transmitir audio en tiempo real durante las llamadas.
    """
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
        f"wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview&temperature={TEMPERATURE}",
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
                if call_log_id and call_sid:
                    try:
                        # Calcular duración si tenemos start_time
                        db = SessionLocal()
                        try:
                            call_log = db.query(CallLog).filter(CallLog.id == call_log_id).first()
                            if call_log and call_log.start_time:
                                from datetime import datetime, timezone
                                duration = int((datetime.now(timezone.utc) - call_log.start_time).total_seconds())
                                
                                # Intentar obtener el recording_url de Twilio si no está guardado
                                recording_url = None
                                if not call_log.recording_url:
                                    try:
                                        recordings = twilio_client.recordings.list(call_sid=call_sid, limit=1)
                                        if recordings:
                                            recording = recordings[0]
                                            recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Recordings/{recording.sid}"
                                            print(f"🎙️ Recording URL obtenido de API: {recording_url}")
                                    except Exception as e:
                                        print(f"⚠️ Error al obtener recording de API: {e}")
                                
                                finish_call(call_log_id, duration_seconds=duration, recording_url=recording_url)
                                print(f"✅ Llamada finalizada: ID={call_log_id}, Duración={duration}s")
                            else:
                                finish_call(call_log_id)
                        finally:
                            db.close()
                    except Exception as e:
                        print(f"❌ Error al finalizar llamada: {e}")
                if openai_ws: #openai_ws.state.name == 'OPEN': (VERSION ANTERIOR)
                    print("Cerrando la sesión de OpenAI Realtime (fin de la llamda)...");
                    try:
                      await openai_ws.close()
                    except:
                      pass

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
                # Cerrando OPENAI (VERSION 2-ADD)
                if openai_ws:
                  print("Cerrando sesión de OpenAI Realtime (error en send_to_twilio)...")
                  try:
                    await openai_ws.close()
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
    phone_number: str | None = None
    contact_id: int | None = None  # Opcional: ID del contacto destino

# IMPORTANTE: Este endpoint REQUIERE autenticación
# Solo usuarios autenticados pueden iniciar llamadas salientes
@router.post("/make-call")
async def make_call(
    request: PhoneNumberRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Inicia una llamada saliente al número de teléfono proporcionado.
    Puede usar contact_id (recomendado) o phone_number directamente.
    
    Este endpoint requiere autenticación - solo usuarios autenticados pueden iniciar llamadas.
    """
    try:
        from app.services.contact_service import get_contact_by_id
        from app.persistance.db import SessionLocal
        from app.models.contact import Contact
        
        # Determinar el número de teléfono destino
        destination_phone = None
        contact_id = None
        
        if request.contact_id:
            # Obtener contacto desde la base de datos
            db = SessionLocal()
            try:
                contact = db.query(Contact).filter_by(id=request.contact_id, is_active=True).first()
                if not contact:
                    raise HTTPException(status_code=404, detail="Contacto no encontrado o inactivo")
                destination_phone = contact.phone_number
                contact_id = contact.id
            finally:
                db.close()
        elif request.phone_number:
            destination_phone = request.phone_number
        else:
            raise HTTPException(status_code=400, detail="Debe proporcionar contact_id o phone_number")
        
        # Obtener la URL base para los webhooks
        phone_number = destination_phone
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
        
        # Realizar la llamada con grabación habilitada
        call = twilio_client.calls.create(
            twiml=str(response),
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            record=True,  # Habilitar grabación
            recording_status_callback=f'https://{domain}/call-status',
            recording_status_callback_method='POST'
        )
        
        print(f"📞 Llamada saliente iniciada - CallSid: {call.sid}, To: {phone_number}, From: {TWILIO_PHONE_NUMBER}")
        
        # Crear CallLog en la base de datos
        if call.sid:
            call_log_id = create_call_log_from_phone_number(
                phone_number_str=TWILIO_PHONE_NUMBER,
                call_sid=call.sid,
                direction="outbound",
                from_number=phone_number,
                contact_id=contact_id,
                to_phone_number=destination_phone
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
            "contact_id": contact_id,
            "twiml": str(response)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))