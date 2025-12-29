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
from sqlalchemy.orm import joinedload

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

# Tiempo de espera después de la despedida antes de colgar (en segundos)
GOODBYE_HANGUP_DELAY = 3.0

if not OPENAI_API_KEY:
    raise ValueError('Llave de OpenAI API no encontrada. Por favor, establecela en el archivo .env.')

def is_goodbye_message(content: str) -> bool:
    """
    Detecta si un mensaje del asistente es una despedida.
    Si es una despedida, la llamada debe colgarse automáticamente.
    """
    if not content:
        return False
    
    content_lower = content.lower().strip()
    
    # Frases comunes de despedida en español e inglés
    goodbye_phrases = [
        "adios",
        "chao",
        "gracias por comunicarte",
        "que tengas un excelente día",
        "que tengas un buen día",
        "gracias por tu tiempo",
        "hasta luego",
        "nos vemos",
        "que estés bien",
        "thank you for calling",
        "have a great day",
        "have a good day",
        "thanks for your time",
        "goodbye",
        "bye",
        "take care",
        "talk to you later",
        "see you later",
        "cuídate",
        "que te vaya bien"
    ]
    
    # Verificar si el contenido contiene alguna frase de despedida
    for phrase in goodbye_phrases:
        if phrase in content_lower:
            return True
    
    return False


def hangup_call(call_sid: str) -> bool:
    """
    Cuelga una llamada usando la API de Twilio.
    Retorna True si se colgó exitosamente, False en caso contrario.
    """
    if not call_sid:
        return False
    
    try:
        # Actualizar el estado de la llamada a 'completed' para colgarla
        call = twilio_client.calls(call_sid).update(status='completed')
        print(f"📞 Llamada colgada automáticamente: CallSid={call_sid}")
        return True
    except Exception as e:
        print(f"❌ Error al colgar llamada {call_sid}: {e}")
        return False


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
        # Esto es importante para llamadas entrantes donde el webhook puede no llegar o llegar tarde
        if call_sid and call_status == "completed":
            # Verificar si ya tenemos el recording en la base de datos
            db_check = SessionLocal()
            try:
                call_log_check = db_check.query(CallLog).filter(CallLog.call_sid == call_sid).first()
                has_recording = call_log_check and (call_log_check.recording_url or call_log_check.recording_sid)
                print(f"🔍 Verificando recording para CallSid {call_sid}: has_recording={has_recording}, recording_sid={recording_sid}, recording_url={recording_url}")
            except Exception as e:
                print(f"⚠️ Error al verificar recording en DB: {e}")
                has_recording = False
            finally:
                db_check.close()
            
            # Solo intentar obtener el recording si no lo tenemos
            if not recording_sid and not recording_url and not has_recording:
                print(f"🔍 Intentando obtener recording de API para CallSid: {call_sid}")
                try:
                    # Esperar un poco para que Twilio procese el recording
                    import time
                    time.sleep(1.0)  # Aumentar espera a 1 segundo
                    
                    # Buscar grabaciones asociadas a esta llamada
                    print(f"🔍 Buscando recordings para CallSid: {call_sid}")
                    recordings = twilio_client.recordings.list(call_sid=call_sid, limit=5)  # Aumentar límite para ver más opciones
                    print(f"📋 Encontrados {len(recordings)} recordings para CallSid: {call_sid}")
                    
                    if recordings:
                        # Tomar el recording más reciente (el primero de la lista)
                        recording = recordings[0]
                        recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Recordings/{recording.sid}"
                        recording_duration_int = None
                        if hasattr(recording, 'duration') and recording.duration:
                            try:
                                recording_duration_int = int(recording.duration)
                            except (ValueError, TypeError):
                                pass
                        
                        print(f"🎙️ Recording encontrado: SID={recording.sid}, Duration={recording_duration_int}s, Status={getattr(recording, 'status', 'N/A')}")
                        
                        success = update_call_recording_url(
                            call_sid, 
                            recording_url,
                            recording_sid=recording.sid,
                            recording_duration=recording_duration_int
                        )
                        if success:
                            print(f"✅ Recording URL obtenido de API y guardado para CallSid: {call_sid}, URL: {recording_url}, SID: {recording.sid}, Duration: {recording_duration_int}s")
                        else:
                            print(f"⚠️ No se pudo guardar el recording en la base de datos")
                    else:
                        print(f"⚠️ No se encontraron recordings para CallSid: {call_sid}")
                        # Intentar buscar por número de teléfono también
                        try:
                            call = twilio_client.calls(call_sid).fetch()
                            if call:
                                print(f"📞 Información de la llamada: From={call.from_}, To={call.to}, Status={call.status}")
                        except Exception as e:
                            print(f"⚠️ Error al obtener información de la llamada: {e}")
                except Exception as e:
                    print(f"⚠️ Error al obtener recording de API (no crítico): {e}")
                    import traceback
                    traceback.print_exc()
        
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
                        # Si es "completed", intentar obtener el recording y actualizar el estado
                        elif call_status == "completed":
                            call_log.end_time = datetime.now(timezone.utc)
                            
                            # Si no tenemos recording, intentar obtenerlo de la API
                            if not call_log.recording_url or not call_log.recording_sid:
                                try:
                                    import time
                                    time.sleep(0.5)  # Pequeña espera para que Twilio procese
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
                                        
                                        call_log.recording_url = recording_url
                                        call_log.recording_sid = recording.sid
                                        if recording_duration_int:
                                            call_log.recording_duration = recording_duration_int
                                        print(f"🎙️ Recording obtenido de API en webhook: URL={recording_url}, SID={recording.sid}, Duration={recording_duration_int}s")
                                except Exception as e:
                                    print(f"⚠️ Error al obtener recording de API en webhook: {e}")
                            
                            # Actualizar el estado correctamente
                            if call_log.recording_duration is not None:
                                # Cargar los turnos si no están cargados
                                if not hasattr(call_log, '_turns_loaded'):
                                    call_log = db.query(CallLog).options(
                                        joinedload(CallLog.turns)
                                    ).filter(CallLog.id == call_log.id).first()
                                from app.services.save_call_to_db import determine_call_status
                                call_log.status = determine_call_status(call_log)
                                call_log.duration_seconds = call_log.recording_duration
                            else:
                                # Si no tenemos recording_duration, usar la duración calculada si hay start_time
                                if call_log.start_time:
                                    duration = int((datetime.now(timezone.utc) - call_log.start_time).total_seconds())
                                    call_log.duration_seconds = duration
                                    # Cargar los turnos para verificar si hubo interacción
                                    if not hasattr(call_log, '_turns_loaded'):
                                        call_log = db.query(CallLog).options(
                                            joinedload(CallLog.turns)
                                        ).filter(CallLog.id == call_log.id).first()
                                    # Marcar como completed si hubo interacción
                                    if call_log.turns and any(turn.speaker == Speaker.user for turn in call_log.turns):
                                        from app.models.call_log import CallStatus
                                        call_log.status = CallStatus.completed
                                    else:
                                        # Si no hay interacción, marcar como no_response
                                        from app.models.call_log import CallStatus
                                        call_log.status = CallStatus.no_response
                        db.commit()
                        print(f"✅ Estado de llamada actualizado: {call_status} -> {call_log.status.value if call_log.status else 'N/A'}")
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
                
                # Actualizar la llamada para habilitar grabación y status callback
                twilio_client.calls(call_sid).update(
                    record=True,
                    recording_status_callback=f'https://{host}/call-status',
                    recording_status_callback_method='POST',
                    status_callback=f'https://{host}/call-status',
                    status_callback_method='POST'
                )
                print(f"✅ Grabación y status callback habilitados para llamada entrante: {call_sid}")
            except Exception as e:
                print(f"⚠️ Error al habilitar grabación (no crítico): {e}")
        
        # Buscar contacto por número de teléfono (si existe)
        contact_id = None
        if from_number:
            try:
                from app.models.contact import Contact
                from app.models.company_phone_number import CompanyPhoneNumber
                
                # Primero obtener la empresa del número que recibe la llamada
                db = SessionLocal()
                try:
                    phone_number_obj = db.query(CompanyPhoneNumber).filter(
                        CompanyPhoneNumber.phone_number == to_number
                    ).first()
                    
                    if phone_number_obj:
                        # Buscar contacto por número de teléfono en la misma empresa
                        contact = db.query(Contact).filter(
                            Contact.phone_number == from_number,
                            Contact.company_id == phone_number_obj.company_id,
                            Contact.is_active == True
                        ).first()
                        
                        if contact:
                            contact_id = contact.id
                            print(f"✅ Contacto encontrado para llamada entrante: ID={contact_id}, Nombre={contact.name}, Teléfono={from_number}")
                        else:
                            print(f"ℹ️ No se encontró contacto para el número: {from_number}")
                    else:
                        print(f"⚠️ No se encontró CompanyPhoneNumber para el número receptor: {to_number}")
                finally:
                    db.close()
            except Exception as e:
                # No fallar la llamada si no se puede buscar el contacto
                print(f"⚠️ Error al buscar contacto (no crítico): {e}")
        
        # Crear CallLog en la base de datos (no crítico si falla)
        if call_sid and to_number:
            try:
                call_log_id = create_call_log_from_phone_number(
                    phone_number_str=to_number,
                    call_sid=call_sid,
                    direction="inbound",
                    from_number=from_number,
                    contact_id=contact_id  # Asociar contacto si se encontró
                )
                if call_log_id:
                    print(f"✅ CallLog creado para llamada entrante: ID={call_log_id}, ContactID={contact_id or 'N/A'}")
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
        
        if not host:
            print("⚠️ No se pudo determinar el host para el WebSocket")
            host = "localhost"  # Fallback
        
        # Limpiar el host (remover http:// o https:// si están presentes)
        if host.startswith(('http://', 'https://')):
            host = host.split('//')[-1].rstrip('/')
        
        # Remover puerto si está presente (Twilio usa el puerto 443 para wss)
        if ':' in host:
            host = host.split(':')[0]
        
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
    
    # Obtener call_sid del query parameter si está disponible
    call_sid_from_query = None
    if websocket.query_params:
        call_sid_from_query = websocket.query_params.get("call_sid")
        if call_sid_from_query:
            print(f"📞 CallSid obtenido del query parameter: {call_sid_from_query}")
    
    # Variables para almacenar datos del agente y contacto
    call_sid = call_sid_from_query
    call_log_id = None
    agent_name = None
    contact_name = None
    custom_prompt = None
    agent_voice = 'coral'
    agent_temperature = TEMPERATURE
    
    # Función para cargar datos del CallLog cuando tengamos el call_sid
    async def load_call_data_from_db(call_sid_param: str):
        """Carga agent_profile y contacto desde el CallLog."""
        nonlocal call_log_id, agent_name, contact_name, custom_prompt, agent_voice, agent_temperature
        
        max_attempts = 5
        for attempt in range(max_attempts):
            db = SessionLocal()
            try:
                call_log = db.query(CallLog).options(
                    joinedload(CallLog.contact)
                ).filter(CallLog.call_sid == call_sid_param).first()
                
                if call_log:
                    call_log_id = call_log.id
                    print(f"✅ CallLog encontrado: ID={call_log_id}, CallSid={call_sid_param}")
                    
                    # Obtener agent_profile desde CallLog
                    if call_log.agent_profile_id:
                        from app.models.agent_profile import AgentProfile
                        agent_profile = db.query(AgentProfile).filter(
                            AgentProfile.id == call_log.agent_profile_id,
                            AgentProfile.is_active == True
                        ).first()
                        
                        if agent_profile:
                            # Verificar que el prompt esté disponible y no esté vacío
                            if agent_profile.prompt and agent_profile.prompt.strip():
                                custom_prompt = agent_profile.prompt.strip()
                                agent_name = agent_profile.name
                                agent_voice = agent_profile.voice or 'coral'
                                agent_temperature = agent_profile.temperature if agent_profile.temperature is not None else TEMPERATURE
                                print(f"🤖 AgentProfile cargado: {agent_profile.name} (Voz: {agent_voice}, Temp: {agent_temperature})")
                                print(f"📝 Prompt disponible: {len(custom_prompt)} caracteres")
                            else:
                                print(f"⚠️ AgentProfile {agent_profile.name} (ID: {agent_profile.id}) no tiene prompt configurado o está vacío")
                        else:
                            print(f"⚠️ AgentProfile ID {call_log.agent_profile_id} no encontrado o inactivo")
                    
                    # Obtener nombre del contacto
                    if call_log.contact:
                        contact_name = call_log.contact.name
                        print(f"👤 Contacto asociado: {contact_name}")
                    elif call_log.to_phone_number:
                        # Para llamadas salientes, buscar contacto por número destino
                        from app.models.contact import Contact
                        if call_log.company_id:
                            contact = db.query(Contact).filter(
                                Contact.phone_number == call_log.to_phone_number,
                                Contact.company_id == call_log.company_id,
                                Contact.is_active == True
                            ).first()
                            if contact:
                                contact_name = contact.name
                                print(f"👤 Contacto encontrado por número: {contact_name}")
                    
                    print(f"📊 Datos cargados - Agent: {agent_name or 'N/A'}, Contact: {contact_name or 'N/A'}")
                    return True
                else:
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(0.5)
                    else:
                        print(f"⚠️ No se encontró CallLog para CallSid: {call_sid_param} después de {max_attempts} intentos")
            except Exception as e:
                print(f"❌ Error al buscar CallLog (intento {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    import traceback
                    traceback.print_exc()
            finally:
                db.close()
        
        return False

    # Función para cargar el prompt y verificar que esté disponible
    async def ensure_prompt_loaded(call_sid_param: str) -> bool:
        """Carga el prompt y verifica que esté disponible. Retorna True si está disponible."""
        max_load_attempts = 10
        for load_attempt in range(max_load_attempts):
            await load_call_data_from_db(call_sid_param)
            
            # Verificar que el prompt esté disponible
            if custom_prompt and custom_prompt.strip():
                print(f"✅ Prompt cargado exitosamente - Agent: {agent_name or 'N/A'}, Contact: {contact_name or 'N/A'}")
                return True
            else:
                if load_attempt < max_load_attempts - 1:
                    wait_time = 0.3 * (load_attempt + 1)  # Espera incremental
                    print(f"⏳ Prompt no disponible aún (intento {load_attempt + 1}/{max_load_attempts}), esperando {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ No se pudo cargar el prompt después de {max_load_attempts} intentos")
        return False
    
    # Intentar cargar datos del CallLog antes de inicializar la sesión (si tenemos call_sid)
    # CRÍTICO: El prompt debe estar disponible antes de inicializar la sesión
    prompt_loaded = False  # Inicializar como False por defecto
    
    if call_sid:
        print(f"🔍 Intentando cargar datos del CallLog antes de inicializar sesión...")
        prompt_loaded = await ensure_prompt_loaded(call_sid)
        
        if not prompt_loaded:
            error_msg = f"ERROR CRÍTICO: No se pudo cargar el prompt del agent_profile para CallSid: {call_sid}. "
            error_msg += "Asegúrate de que el agent_profile tenga un prompt configurado en la base de datos."
            print(error_msg)
            raise ValueError(error_msg)
    else:
        print(f"⚠️ No hay call_sid en query parameters. Esperando evento 'start' para obtener call_sid...")
    
    async with websockets.connect(
        f"wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview&temperature={agent_temperature}",
        additional_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
    ) as openai_ws:
        # Inicializar sesión solo si el prompt ya está cargado
        # Si no está cargado, esperaremos al evento 'start' para cargarlo y actualizar la sesión
        if prompt_loaded:
            await initialize_session(
                openai_ws,
                custom_prompt=custom_prompt,
                contact_name=contact_name,
                agent_name=agent_name,
                voice=agent_voice,
                temperature=agent_temperature
            )
        else:
            print(f"⏳ Inicializando sesión sin prompt (se actualizará cuando llegue el evento 'start')...")
            # Inicializar con un prompt temporal mínimo para evitar errores
            # Este prompt será reemplazado cuando llegue el evento 'start'
            await initialize_session(
                openai_ws,
                custom_prompt="You are a helpful assistant. Please wait for instructions.",
                contact_name=None,
                agent_name=None,
                voice=agent_voice,
                temperature=agent_temperature
            )

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
            
            # Función auxiliar para finalizar la llamada cuando se desconecta
            async def finalize_call_on_disconnect():
                """Finaliza la llamada cuando el WebSocket se desconecta."""
                nonlocal call_sid, call_log_id
                
                # Si no tenemos call_log_id pero tenemos call_sid, buscarlo
                if not call_log_id and call_sid:
                    db_lookup = SessionLocal()
                    try:
                        call_log_lookup = db_lookup.query(CallLog).filter(CallLog.call_sid == call_sid).first()
                        if call_log_lookup:
                            call_log_id = call_log_lookup.id
                            print(f"✅ CallLog encontrado por call_sid al desconectar: ID={call_log_id}, CallSid={call_sid}")
                    except Exception as e:
                        print(f"⚠️ Error al buscar CallLog por call_sid: {e}")
                    finally:
                        db_lookup.close()
                
                if call_log_id and call_sid:
                    try:
                        print(f"🔄 Iniciando finalización de llamada: CallLogID={call_log_id}, CallSid={call_sid}")
                        # Esperar un poco para que Twilio procese el recording
                        await asyncio.sleep(2.0)  # Aumentar espera a 2 segundos
                        
                        # Calcular duración si tenemos start_time
                        db = SessionLocal()
                        try:
                            call_log = db.query(CallLog).options(
                                joinedload(CallLog.turns)
                            ).filter(CallLog.id == call_log_id).first()
                            
                            if call_log:
                                print(f"📊 CallLog encontrado: Status actual={call_log.status.value if call_log.status else 'N/A'}, StartTime={call_log.start_time}, EndTime={call_log.end_time}")
                                
                                if call_log.start_time:
                                    duration = int((datetime.now(timezone.utc) - call_log.start_time).total_seconds())
                                    print(f"⏱️ Duración calculada: {duration}s")
                                    
                                    # Intentar obtener el recording de Twilio si no está guardado
                                    if not call_log.recording_url or not call_log.recording_sid:
                                        print(f"🔍 Buscando recording en Twilio API para CallSid: {call_sid}...")
                                        try:
                                            # Intentar múltiples veces con diferentes esperas
                                            for attempt in range(3):
                                                await asyncio.sleep(1.0 + attempt * 0.5)  # 1s, 1.5s, 2s
                                                recordings = twilio_client.recordings.list(call_sid=call_sid, limit=5)
                                                print(f"🔍 Intento {attempt + 1}: Encontrados {len(recordings)} recordings")
                                                
                                                if recordings:
                                                    # Tomar el recording más reciente
                                                    recording = recordings[0]
                                                    recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Recordings/{recording.sid}"
                                                    recording_duration_int = None
                                                    if hasattr(recording, 'duration') and recording.duration:
                                                        try:
                                                            recording_duration_int = int(recording.duration)
                                                        except (ValueError, TypeError):
                                                            pass
                                                    
                                                    # Actualizar el recording en la base de datos
                                                    call_log.recording_url = recording_url
                                                    call_log.recording_sid = recording.sid
                                                    if recording_duration_int:
                                                        call_log.recording_duration = recording_duration_int
                                                    print(f"🎙️ Recording obtenido de API al desconectar: URL={recording_url}, SID={recording.sid}, Duration={recording_duration_int}s")
                                                    break  # Salir del loop si encontramos el recording
                                                else:
                                                    print(f"⚠️ Intento {attempt + 1}: No se encontraron recordings, reintentando...")
                                            
                                            if not call_log.recording_url or not call_log.recording_sid:
                                                print(f"⚠️ No se encontraron recordings después de 3 intentos para CallSid: {call_sid}")
                                        except Exception as e:
                                            print(f"⚠️ Error al obtener recording de API: {e}")
                                            import traceback
                                            traceback.print_exc()
                                
                                # Actualizar el estado correctamente
                                call_log.end_time = datetime.now(timezone.utc)
                                
                                # Si tenemos recording_duration, usarlo y determinar el estado correcto
                                if call_log.recording_duration is not None:
                                    call_log.duration_seconds = call_log.recording_duration
                                    from app.services.save_call_to_db import determine_call_status
                                    call_log.status = determine_call_status(call_log)
                                    print(f"✅ Estado determinado por recording_duration: {call_log.status.value}")
                                else:
                                    # Si no tenemos recording_duration, usar la duración calculada
                                    if call_log.start_time:
                                        call_log.duration_seconds = duration
                                        # Marcar como completed si hubo interacción (hay turnos del usuario)
                                        if call_log.turns and any(turn.speaker == Speaker.user for turn in call_log.turns):
                                            from app.models.call_log import CallStatus
                                            call_log.status = CallStatus.completed
                                            print(f"✅ Estado actualizado a completed (hay turnos del usuario)")
                                        else:
                                            # Si no hay interacción pero la llamada terminó, marcar como no_response
                                            from app.models.call_log import CallStatus
                                            call_log.status = CallStatus.no_response
                                            print(f"✅ Estado actualizado a no_response (no hay turnos del usuario)")
                                
                                db.commit()
                                print(f"✅ Llamada finalizada al desconectar: ID={call_log_id}, Status={call_log.status.value if call_log.status else 'N/A'}, Duración={call_log.duration_seconds}s, Recording: {call_log.recording_url or 'N/A'}")
                                
                                # Si aún no tenemos recording después de 2 segundos, intentar nuevamente después de más tiempo
                                if not call_log.recording_url or not call_log.recording_sid:
                                    print(f"⚠️ Recording aún no disponible, programando reintento...")
                                    # Programar un task asíncrono para intentar obtener el recording más tarde
                                    async def retry_get_recording():
                                        await asyncio.sleep(5.0)  # Esperar 5 segundos más
                                        try:
                                            db_retry = SessionLocal()
                                            try:
                                                call_log_retry = db_retry.query(CallLog).filter(CallLog.id == call_log_id).first()
                                                if call_log_retry and (not call_log_retry.recording_url or not call_log_retry.recording_sid):
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
                                                        
                                                        call_log_retry.recording_url = recording_url
                                                        call_log_retry.recording_sid = recording.sid
                                                        if recording_duration_int:
                                                            call_log_retry.recording_duration = recording_duration_int
                                                            call_log_retry.duration_seconds = recording_duration_int
                                                            from app.services.save_call_to_db import determine_call_status
                                                            call_log_retry.status = determine_call_status(call_log_retry)
                                                        db_retry.commit()
                                                        print(f"✅ Recording obtenido en reintento: URL={recording_url}, SID={recording.sid}, Duration={recording_duration_int}s")
                                            finally:
                                                db_retry.close()
                                        except Exception as e:
                                            print(f"⚠️ Error en reintento de recording: {e}")
                                    
                                    # Crear task para reintento (no esperar)
                                    asyncio.create_task(retry_get_recording())
                            else:
                                # Si no tenemos start_time, solo actualizar end_time
                                if call_log:
                                    call_log.end_time = datetime.now(timezone.utc)
                                    db.commit()
                                    print(f"✅ End_time actualizado para CallLog sin start_time")
                        finally:
                            db.close()
                    except Exception as e:
                        print(f"❌ Error al finalizar llamada: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"⚠️ No se puede finalizar llamada: call_log_id={call_log_id}, call_sid={call_sid}")
            
            # Asegurar que call_sid esté disponible para send_to_twilio
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
                        call_sid_from_event = data['start'].get('callSid')
                        # Actualizar call_sid en el scope principal
                        call_sid = call_sid_from_event
                        print(f"📞 CallSid obtenido del evento start: {call_sid}")
                        
                        # Cargar datos del CallLog (agente y contacto) y actualizar sesión
                        if call_sid:
                            # Intentar cargar el prompt con múltiples intentos
                            prompt_loaded = await ensure_prompt_loaded(call_sid)
                            
                            if not prompt_loaded:
                                error_msg = f"ERROR CRÍTICO: No se pudo cargar el prompt del agent_profile para CallSid: {call_sid}. "
                                error_msg += "Asegúrate de que el agent_profile tenga un prompt configurado en la base de datos."
                                print(error_msg)
                                # No lanzar error aquí, solo registrar y continuar
                            else:
                                # Actualizar la sesión de OpenAI con los datos correctos
                                # Usar la función build_instructions para construir el prompt correctamente
                                from app.services.openai_service import build_instructions
                                
                                instructions = build_instructions(
                                    custom_prompt=custom_prompt,
                                    contact_name=contact_name,
                                    agent_name=agent_name
                                )
                                
                                # Construir y enviar el session_update
                                session_update = {
                                    "type": "session.update",
                                    "session": {
                                        "type": "realtime",
                                        "instructions": instructions,
                                        "audio": {
                                            "output": {
                                                "format": {"type": "audio/pcmu"},
                                                "voice": agent_voice
                                            }
                                        }
                                    }
                                }
                                
                                await openai_ws.send(json.dumps(session_update))
                                print(f"✅ Sesión actualizada - Agent: {agent_name or 'N/A'}, Contact: {contact_name or 'N/A'}, Prompt: Custom")
                        
                        print(f"Incoming stream has started {stream_sid}, CallSid: {call_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except WebSocketDisconnect:
                print("🔌 Cliente desconectado (usuario colgó o conexión perdida).")
                # Finalizar la llamada usando la función auxiliar
                await finalize_call_on_disconnect()
                if openai_ws:
                    try:
                        await openai_ws.close()
                    except:
                        pass

        async def send_to_twilio():
            """Recibe eventos de la API de OpenAI Realtime y envía audio de vuelta a Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, current_user_transcription, current_assistant_content, call_sid, call_log_id
            goodbye_detected = False
            goodbye_timestamp = None
            hangup_task = None
            
            async def schedule_hangup():
                """Programa el cierre de la llamada después de un delay."""
                nonlocal goodbye_detected, goodbye_timestamp, call_sid, hangup_task, call_log_id
                try:
                    if goodbye_detected and call_sid:
                        await asyncio.sleep(GOODBYE_HANGUP_DELAY)
                        # Verificar nuevamente antes de colgar (por si el usuario habló)
                        if goodbye_detected and call_sid:
                            print(f"⏰ Tiempo de espera completado, colgando llamada...")
                            # Colgar la llamada en Twilio
                            hangup_call(call_sid)
                            
                            # Actualizar el estado en la base de datos
                            if call_log_id:
                                try:
                                    # Esperar un poco para que Twilio procese el recording
                                    await asyncio.sleep(1.0)
                                    
                                    # Calcular duración si tenemos start_time
                                    db = SessionLocal()
                                    try:
                                        call_log = db.query(CallLog).options(
                                            joinedload(CallLog.turns)
                                        ).filter(CallLog.id == call_log_id).first()
                                        if call_log and call_log.start_time:
                                            duration = int((datetime.now(timezone.utc) - call_log.start_time).total_seconds())
                                            
                                            # Intentar obtener el recording de Twilio si no está guardado
                                            if not call_log.recording_url or not call_log.recording_sid:
                                                try:
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
                                                        
                                                        # Actualizar el recording en la base de datos
                                                        call_log.recording_url = recording_url
                                                        call_log.recording_sid = recording.sid
                                                        if recording_duration_int:
                                                            call_log.recording_duration = recording_duration_int
                                                        print(f"🎙️ Recording obtenido de API después de colgar: URL={recording_url}, SID={recording.sid}, Duration={recording_duration_int}s")
                                                except Exception as e:
                                                    print(f"⚠️ Error al obtener recording de API después de colgar: {e}")
                                            
                                            # Si tenemos recording_duration, usarlo y determinar el estado correcto
                                            if call_log.recording_duration is not None:
                                                call_log.duration_seconds = call_log.recording_duration
                                                from app.services.save_call_to_db import determine_call_status
                                                call_log.status = determine_call_status(call_log)
                                            else:
                                                # Si no tenemos recording_duration, usar la duración calculada
                                                call_log.duration_seconds = duration
                                                # Marcar como completed si hubo interacción (hay turnos del usuario)
                                                if call_log.turns and any(turn.speaker == Speaker.user for turn in call_log.turns):
                                                    from app.models.call_log import CallStatus
                                                    call_log.status = CallStatus.completed
                                            
                                            call_log.end_time = datetime.now(timezone.utc)
                                            db.commit()
                                            print(f"✅ Estado de llamada actualizado después de colgar: Status={call_log.status.value if call_log.status else 'N/A'}, Duración={call_log.duration_seconds}s, Recording: {call_log.recording_url or 'N/A'}")
                                        else:
                                            # Si no tenemos start_time, solo actualizar end_time
                                            if call_log:
                                                call_log.end_time = datetime.now(timezone.utc)
                                                db.commit()
                                    except Exception as e:
                                        db.rollback()
                                        print(f"⚠️ Error al actualizar estado después de colgar: {e}")
                                    finally:
                                        db.close()
                                except Exception as e:
                                    print(f"⚠️ Error al actualizar estado en base de datos: {e}")
                            
                            goodbye_detected = False
                            goodbye_timestamp = None
                            hangup_task = None
                except asyncio.CancelledError:
                    print(f"🔄 Cierre automático cancelado (usuario habló)")
                    hangup_task = None
                    raise
            
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
                            # Si el usuario habla después de una despedida, cancelar el cierre automático
                            if goodbye_detected:
                                print(f"🔄 Usuario habló después de la despedida, cancelando cierre automático")
                                goodbye_detected = False
                                goodbye_timestamp = None
                                if hangup_task and not hangup_task.done():
                                    hangup_task.cancel()
                                    hangup_task = None
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
                                        # Si el usuario habla después de una despedida, cancelar el cierre automático
                                        if goodbye_detected:
                                            print(f"🔄 Usuario habló después de la despedida, cancelando cierre automático")
                                            goodbye_detected = False
                                            goodbye_timestamp = None
                                            if hangup_task and not hangup_task.done():
                                                hangup_task.cancel()
                                                hangup_task = None
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
                                        
                                        # Detectar si es una despedida
                                        if is_goodbye_message(transcript_text):
                                            goodbye_detected = True
                                            goodbye_timestamp = asyncio.get_event_loop().time()
                                            print(f"👋 Despedida detectada, la llamada se colgará en {GOODBYE_HANGUP_DELAY} segundos")
                                            # Programar el cierre después de que termine la respuesta
                                            if call_sid and not hangup_task:
                                                hangup_task = asyncio.create_task(schedule_hangup())
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
                                    
                                    # Detectar si es una despedida
                                    if is_goodbye_message(text_content):
                                        goodbye_detected = True
                                        goodbye_timestamp = asyncio.get_event_loop().time()
                                        print(f"👋 Despedida detectada, la llamada se colgará en {GOODBYE_HANGUP_DELAY} segundos")
                                        # Programar el cierre después de que termine la respuesta
                                        if call_sid and not hangup_task:
                                            hangup_task = asyncio.create_task(schedule_hangup())
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
                        # Si el usuario habla después de una despedida, cancelar el cierre automático
                        if goodbye_detected:
                            print(f"🔄 Usuario empezó a hablar después de la despedida, cancelando cierre automático")
                            goodbye_detected = False
                            goodbye_timestamp = None
                            if hangup_task and not hangup_task.done():
                                hangup_task.cancel()
                                hangup_task = None
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
    agent_profile_id: int | None = None  # Opcional: ID del agent_profile a usar (si no se especifica, usa el activo de la empresa)

# IMPORTANTE: Este endpoint REQUIERE autenticación
# Solo usuarios autenticados pueden iniciar llamadas salientes
def prepare_call_data(
    request: PhoneNumberRequest,
    current_user: User
) -> dict:
    """
    Prepara los datos necesarios para realizar una llamada:
    1. Obtiene el agente (especificado o activo de la empresa)
    2. Obtiene el contacto (si está disponible)
    3. Valida que exista un agente activo
    
    Returns:
        dict con: agent_profile, contact, destination_phone, company_id, contact_id, contact_name
        
    Raises:
        HTTPException si no hay agente activo o datos inválidos
    """
    from app.persistance.db import SessionLocal
    from app.models.contact import Contact
    from app.models.agent_profile import AgentProfile
    from app.models.company_phone_number import CompanyPhoneNumber
    
    db = SessionLocal()
    try:
        # ============================================
        # PASO 1: Obtener contacto y determinar company_id
        # ============================================
        destination_phone = None
        contact_id = None
        contact_name = None
        company_id = None
        
        if request.contact_id:
            contact = db.query(Contact).filter_by(id=request.contact_id, is_active=True).first()
            if not contact:
                raise HTTPException(status_code=404, detail="Contacto no encontrado o inactivo")
            destination_phone = contact.phone_number
            contact_id = contact.id
            contact_name = contact.name
            company_id = contact.company_id
            print(f"✅ Contacto obtenido: {contact_name} ({destination_phone}), CompanyID: {company_id}")
        elif request.phone_number:
            destination_phone = request.phone_number
            # Obtener company_id del número de teléfono de Twilio
            phone_number_obj = db.query(CompanyPhoneNumber).filter(
                CompanyPhoneNumber.phone_number == TWILIO_PHONE_NUMBER
            ).first()
            if phone_number_obj:
                company_id = phone_number_obj.company_id
                # Buscar contacto por número si existe
                contact = db.query(Contact).filter(
                    Contact.phone_number == destination_phone,
                    Contact.company_id == company_id,
                    Contact.is_active == True
                ).first()
                if contact:
                    contact_id = contact.id
                    contact_name = contact.name
                    print(f"✅ Contacto encontrado por número: {contact_name}")
            else:
                raise HTTPException(status_code=400, detail="No se pudo determinar la empresa para la llamada")
        else:
            raise HTTPException(status_code=400, detail="Debe proporcionar contact_id o phone_number")
        
        if not company_id:
            raise HTTPException(status_code=400, detail="No se pudo determinar la empresa para la llamada")
        
        # ============================================
        # PASO 2: Obtener agent_profile (OBLIGATORIO)
        # ============================================
        agent_profile = None
        
        if request.agent_profile_id:
            # Buscar el agent_profile específico
            agent_profile = db.query(AgentProfile).filter(
                AgentProfile.id == request.agent_profile_id,
                AgentProfile.company_id == company_id,
                AgentProfile.is_active == True
            ).first()
            
            if agent_profile:
                print(f"✅ AgentProfile especificado encontrado: {agent_profile.name} (ID: {agent_profile.id})")
            else:
                raise HTTPException(
                    status_code=404, 
                    detail=f"AgentProfile ID {request.agent_profile_id} no encontrado, inactivo o no pertenece a la empresa"
                )
        
        # Si no se especificó, buscar el activo de la empresa
        if not agent_profile:
            agent_profile = db.query(AgentProfile).filter(
                AgentProfile.company_id == company_id,
                AgentProfile.is_active == True
            ).first()
            
            if agent_profile:
                print(f"✅ AgentProfile activo encontrado: {agent_profile.name} (ID: {agent_profile.id})")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"No hay AgentProfile activo para la empresa. Debe crear un agente antes de realizar llamadas."
                )
        
        return {
            "agent_profile": agent_profile,
            "contact_id": contact_id,
            "contact_name": contact_name,
            "destination_phone": destination_phone,
            "company_id": company_id
        }
    finally:
        db.close()


@router.post("/make-call")
async def make_call(
    request: PhoneNumberRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Inicia una llamada saliente al número de teléfono proporcionado.
    Requiere que exista un AgentProfile activo para la empresa.
    
    Este endpoint requiere autenticación - solo usuarios autenticados pueden iniciar llamadas.
    """
    try:
        # ============================================
        # PASO 1: Preparar datos (agente y contacto)
        # ============================================
        call_data = prepare_call_data(request, current_user)
        agent_profile = call_data["agent_profile"]
        contact_id = call_data["contact_id"]
        contact_name = call_data["contact_name"]
        destination_phone = call_data["destination_phone"]
        company_id = call_data["company_id"]
        
        # ============================================
        # PASO 2: Construir TwiML y iniciar llamada
        # ============================================
        host = os.getenv('HOST')
        if not host:
            # Si no hay HOST configurado, usar el hostname de la request
            # Esto es un fallback, pero debería configurarse HOST en producción
            raise HTTPException(status_code=500, detail="HOST no configurado en variables de entorno")
        
        # Limpiar el host (remover http:// o https:// si están presentes)
        if host.startswith(('http://', 'https://')):
            domain = host.split('//')[-1].rstrip('/')
        else:
            domain = host.rstrip('/')
        
        response = VoiceResponse()
        connect = Connect()
        connect.stream(url=f'wss://{domain}/media-stream')
        response.append(connect)
        
        call = twilio_client.calls.create(
            twiml=str(response),
            to=destination_phone,
            from_=TWILIO_PHONE_NUMBER,
            record=True,
            recording_status_callback=f'https://{domain}/call-status',
            recording_status_callback_method='POST'
        )
        
        print(f"📞 Llamada saliente iniciada - CallSid: {call.sid}, To: {destination_phone}, From: {TWILIO_PHONE_NUMBER}")
        print(f"📋 Datos preparados - Agent: {agent_profile.name} (ID: {agent_profile.id}), Contact: {contact_name or 'N/A'}")
        
        # ============================================
        # PASO 3: Crear CallLog con agent_profile_id
        # ============================================
        if call.sid:
            call_log_id = create_call_log_from_phone_number(
                phone_number_str=TWILIO_PHONE_NUMBER,
                call_sid=call.sid,
                direction="outbound",
                from_number=None,
                contact_id=contact_id,
                to_phone_number=destination_phone,
                agent_profile_id=agent_profile.id
            )
            if call_log_id:
                print(f"✅ CallLog creado: ID={call_log_id}, AgentProfileID={agent_profile.id}")
            else:
                print(f"⚠️ No se pudo crear CallLog para la llamada saliente")
        
        return {
            "status": "Llamada iniciada",
            "call_sid": call.sid,
            "to": destination_phone,
            "from": TWILIO_PHONE_NUMBER,
            "contact_id": contact_id,
            "contact_name": contact_name,
            "agent_profile_id": agent_profile.id,
            "agent_name": agent_profile.name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))