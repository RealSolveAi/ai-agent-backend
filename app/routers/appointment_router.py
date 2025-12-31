# app/routers/appointment_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.routers.auth_router import get_current_user
from app.models.user import User
from app.models.appointment_reminder import ReminderType
from app.services import appointment_service
from app.services.reminder_scheduler import create_reminder, delete_reminder
from app.services.twilio_service import make_call_internal

router = APIRouter(prefix="/appointments", tags=["Appointments"])


# ============================================
# Pydantic Models (Request/Response)
# ============================================

class AppointmentCreate(BaseModel):
    contact_id: int
    title: str
    description: Optional[str] = None
    scheduled_datetime: datetime  # Puede ser en zona local, se convertirá a UTC
    duration_minutes: int = 30
    agent_profile_id: Optional[int] = None
    timezone: Optional[str] = None  # Si no se proporciona, usa la de la empresa


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    agent_profile_id: Optional[int] = None
    notes: Optional[str] = None
    timezone: Optional[str] = None


class ReminderCreate(BaseModel):
    reminder_type: ReminderType
    time_before_minutes: int  # Minutos antes de la cita (ej: 60 = 1 hora, 1440 = 1 día)


# ============================================
# Endpoints
# ============================================

@router.post("")
async def create_appointment(
    appointment: AppointmentCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Crea una nueva cita programada.
    
    - **contact_id**: ID del contacto
    - **title**: Título de la cita
    - **scheduled_datetime**: Fecha/hora programada (en zona local o UTC)
    - **duration_minutes**: Duración en minutos (default: 30)
    - **agent_profile_id**: ID del agente (opcional, usa el activo de la empresa)
    - **timezone**: Zona horaria (opcional, usa la de la empresa)
    """
    try:
        new_appointment = appointment_service.create_appointment(
            company_id=current_user.company_id,
            contact_id=appointment.contact_id,
            title=appointment.title,
            scheduled_datetime=appointment.scheduled_datetime,
            agent_profile_id=appointment.agent_profile_id,
            description=appointment.description,
            duration_minutes=appointment.duration_minutes,
            appointment_timezone=appointment.timezone
        )
        
        return {
            "message": "Cita creada exitosamente",
            "appointment_id": new_appointment.id,
            "scheduled_datetime": new_appointment.scheduled_datetime,
            "timezone": new_appointment.timezone
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_appointments(
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    contact_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    Obtiene las citas de la empresa con filtros opcionales.
    
    - **limit**: Límite de resultados (default: 50, max: 100)
    - **offset**: Offset para paginación
    - **status**: Filtrar por estado (scheduled, completed, cancelled, etc.)
    - **contact_id**: Filtrar por contacto
    - **start_date**: Fecha de inicio (UTC)
    - **end_date**: Fecha de fin (UTC)
    """
    try:
        appointments = appointment_service.get_appointments_by_company(
            company_id=current_user.company_id,
            limit=limit,
            offset=offset,
            status=status,
            contact_id=contact_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "appointments": appointments,
            "count": len(appointments)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming")
async def get_upcoming_appointments(
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Obtiene las próximas citas programadas de la empresa.
    Útil para mostrar en un dashboard.
    
    - **limit**: Número máximo de citas a retornar (default: 10, max: 50)
    """
    try:
        appointments = appointment_service.get_upcoming_appointments(
            company_id=current_user.company_id,
            limit=limit
        )
        
        return {
            "upcoming_appointments": appointments,
            "count": len(appointments)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar/{year}/{month}")
async def get_calendar_month(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todas las citas de un mes específico agrupadas por día.
    Útil para renderizar un calendario mensual en el frontend.
    
    - **year**: Año (ej: 2025)
    - **month**: Mes (1-12)
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12")
    
    try:
        appointments_by_day = appointment_service.get_appointments_by_month(
            company_id=current_user.company_id,
            year=year,
            month=month
        )
        
        return {
            "year": year,
            "month": month,
            "appointments_by_day": appointments_by_day
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el detalle completo de una cita incluyendo recordatorios.
    
    - **appointment_id**: ID de la cita
    """
    try:
        appointment = appointment_service.get_appointment_detail(appointment_id)
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        
        # Verificar que la cita pertenece a la empresa del usuario
        if appointment["company_id"] != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes permiso para ver esta cita")
        
        return appointment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{appointment_id}")
async def update_appointment(
    appointment_id: int,
    appointment_update: AppointmentUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza una cita existente.
    
    - **appointment_id**: ID de la cita
    - Los campos son opcionales, solo se actualizan los proporcionados
    """
    try:
        # Verificar que la cita existe y pertenece a la empresa
        appointment = appointment_service.get_appointment_detail(appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        
        if appointment["company_id"] != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes permiso para modificar esta cita")
        
        # Actualizar la cita
        updated_appointment = appointment_service.update_appointment(
            appointment_id=appointment_id,
            title=appointment_update.title,
            description=appointment_update.description,
            scheduled_datetime=appointment_update.scheduled_datetime,
            duration_minutes=appointment_update.duration_minutes,
            agent_profile_id=appointment_update.agent_profile_id,
            notes=appointment_update.notes,
            appointment_timezone=appointment_update.timezone
        )
        
        # Si se actualizó la fecha/hora, reprogramar recordatorios
        if appointment_update.scheduled_datetime is not None:
            from app.services.reminder_scheduler import reschedule_appointment_reminders
            reschedule_appointment_reminders(appointment_id)
        
        return {
            "message": "Cita actualizada exitosamente",
            "appointment_id": updated_appointment.id
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{appointment_id}")
async def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Cancela una cita (no la elimina, solo cambia su estado a 'cancelled').
    También cancela todos los recordatorios pendientes.
    
    - **appointment_id**: ID de la cita
    """
    try:
        # Verificar que la cita existe y pertenece a la empresa
        appointment = appointment_service.get_appointment_detail(appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        
        if appointment["company_id"] != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes permiso para cancelar esta cita")
        
        # Cancelar la cita
        cancelled_appointment = appointment_service.cancel_appointment(appointment_id)
        
        return {
            "message": "Cita cancelada exitosamente",
            "appointment_id": cancelled_appointment.id,
            "cancelled_at": cancelled_appointment.cancelled_at
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{appointment_id}/reminders")
async def add_reminder(
    appointment_id: int,
    reminder: ReminderCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Agrega un recordatorio a una cita.
    
    - **appointment_id**: ID de la cita
    - **reminder_type**: Tipo de recordatorio (notification, call, both)
    - **time_before_minutes**: Minutos antes de la cita (ej: 60 = 1 hora, 1440 = 1 día)
    """
    try:
        # Verificar que la cita existe y pertenece a la empresa
        appointment = appointment_service.get_appointment_detail(appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        
        if appointment["company_id"] != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes permiso para modificar esta cita")
        
        # Crear el recordatorio
        new_reminder = create_reminder(
            appointment_id=appointment_id,
            reminder_type=reminder.reminder_type,
            time_before_minutes=reminder.time_before_minutes
        )
        
        return {
            "message": "Recordatorio creado exitosamente",
            "reminder_id": new_reminder.id,
            "reminder_datetime": new_reminder.reminder_datetime,
            "reminder_type": new_reminder.reminder_type.value
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{appointment_id}/reminders/{reminder_id}")
async def remove_reminder(
    appointment_id: int,
    reminder_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Elimina un recordatorio de una cita.
    
    - **appointment_id**: ID de la cita
    - **reminder_id**: ID del recordatorio
    """
    try:
        # Verificar que la cita existe y pertenece a la empresa
        appointment = appointment_service.get_appointment_detail(appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        
        if appointment["company_id"] != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes permiso para modificar esta cita")
        
        # Eliminar el recordatorio
        delete_reminder(reminder_id)
        
        return {
            "message": "Recordatorio eliminado exitosamente",
            "reminder_id": reminder_id
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{appointment_id}/call")
async def trigger_appointment_call(
    appointment_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Inicia una llamada inmediata para una cita (sin esperar al recordatorio programado).
    Útil para llamar manualmente antes de la hora programada.
    
    - **appointment_id**: ID de la cita
    """
    try:
        # Verificar que la cita existe y pertenece a la empresa
        appointment = appointment_service.get_appointment_detail(appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        
        if appointment["company_id"] != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes permiso para realizar esta acción")
        
        # Verificar que la cita no esté cancelada
        if appointment["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="No se puede llamar a una cita cancelada")
        
        # Realizar la llamada
        contact = appointment["contact"]
        if not contact:
            raise HTTPException(status_code=400, detail="La cita no tiene un contacto asociado")
        
        call_result = make_call_internal(
            to_phone_number=contact["phone_number"],
            company_id=appointment["company_id"],
            contact_id=contact["id"],
            agent_profile_id=appointment["agent_profile"]["id"] if appointment["agent_profile"] else None,
            appointment_id=appointment_id
        )
        
        # Actualizar estado de la cita a in_progress
        appointment_service.update_appointment(
            appointment_id=appointment_id,
            notes=f"Llamada manual iniciada - CallSid: {call_result['call_sid']}"
        )
        
        return {
            "message": "Llamada iniciada exitosamente",
            "call_sid": call_result["call_sid"],
            "to": call_result["to"],
            "contact_name": contact["name"]
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
