# app/services/appointment_service.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_, extract
from app.persistance.db import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.appointment_reminder import AppointmentReminder, ReminderType, ReminderStatus
from app.models.contact import Contact
from app.models.agent_profile import AgentProfile
from app.models.company import Company
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import pytz


def create_appointment(
    company_id: int,
    contact_id: int,
    title: str,
    scheduled_datetime: datetime,
    agent_profile_id: Optional[int] = None,
    description: Optional[str] = None,
    duration_minutes: int = 30,
    appointment_timezone: Optional[str] = None
):
    """
    Crea una nueva cita programada.
    
    Args:
        company_id: ID de la empresa
        contact_id: ID del contacto
        title: Título de la cita
        scheduled_datetime: Fecha/hora programada (puede ser en zona local o UTC)
        agent_profile_id: ID del perfil de agente (opcional, usa el activo de la empresa)
        description: Descripción de la cita
        duration_minutes: Duración en minutos
        appointment_timezone: Zona horaria (si no se proporciona, usa la de la empresa)
    
    Returns:
        Appointment creado
    """
    db = SessionLocal()
    try:
        # Validar que el contacto existe y pertenece a la empresa
        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.company_id == company_id
        ).first()
        
        if not contact:
            raise ValueError(f"Contacto {contact_id} no encontrado o no pertenece a la empresa {company_id}")
        
        # Obtener zona horaria
        if not appointment_timezone:
            # Intentar obtener de la empresa
            company = db.query(Company).filter(Company.id == company_id).first()
            appointment_timezone = company.timezone if company else "UTC"
        
        # Asegurar que scheduled_datetime esté en UTC
        if scheduled_datetime.tzinfo is None:
            # Si no tiene timezone, asumimos que está en la zona horaria especificada
            local_tz = pytz.timezone(appointment_timezone)
            scheduled_datetime = local_tz.localize(scheduled_datetime)
        
        # Convertir a UTC para guardar
        scheduled_datetime_utc = scheduled_datetime.astimezone(pytz.UTC)
        
        # Validar agent_profile_id si se proporciona
        if agent_profile_id:
            agent_profile = db.query(AgentProfile).filter(AgentProfile.id == agent_profile_id).first()
            if not agent_profile:
                raise ValueError(f"Perfil de agente {agent_profile_id} no encontrado")
            if agent_profile.company_id != company_id:
                raise ValueError(f"El perfil de agente {agent_profile_id} no pertenece a la empresa {company_id}")
        else:
            # Si no se especifica agent_profile_id, usar el activo de la empresa
            agent_profile = db.query(AgentProfile).filter(
                AgentProfile.company_id == company_id,
                AgentProfile.is_active == True
            ).first()
            
            if agent_profile:
                agent_profile_id = agent_profile.id
        
        # Crear la cita
        appointment = Appointment(
            company_id=company_id,
            contact_id=contact_id,
            agent_profile_id=agent_profile_id,
            title=title,
            description=description,
            scheduled_datetime=scheduled_datetime_utc,
            duration_minutes=duration_minutes,
            timezone=appointment_timezone,
            status=AppointmentStatus.scheduled
        )
        
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        
        return appointment
        
    finally:
        db.close()


def get_appointments_by_company(
    company_id: int,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    contact_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    Obtiene las citas de una empresa con filtros opcionales.
    
    Args:
        company_id: ID de la empresa
        limit: Límite de resultados
        offset: Offset para paginación
        status: Filtrar por estado (scheduled, completed, cancelled, etc.)
        contact_id: Filtrar por contacto
        start_date: Fecha de inicio (UTC)
        end_date: Fecha de fin (UTC)
    
    Returns:
        Lista de citas con información relacionada
    """
    db = SessionLocal()
    try:
        query = db.query(Appointment).filter(Appointment.company_id == company_id)
        
        # Aplicar filtros
        if status:
            query = query.filter(Appointment.status == status)
        
        if contact_id:
            query = query.filter(Appointment.contact_id == contact_id)
        
        if start_date:
            query = query.filter(Appointment.scheduled_datetime >= start_date)
        
        if end_date:
            query = query.filter(Appointment.scheduled_datetime <= end_date)
        
        # Cargar relaciones
        query = query.options(
            joinedload(Appointment.contact),
            joinedload(Appointment.agent_profile),
            joinedload(Appointment.call_log),
            joinedload(Appointment.reminders)
        )
        
        # Ordenar por fecha programada (más recientes primero)
        query = query.order_by(desc(Appointment.scheduled_datetime))
        
        # Paginación
        appointments = query.limit(limit).offset(offset).all()
        
        # Convertir a diccionarios con información relevante
        result = []
        for apt in appointments:
            result.append({
                "id": apt.id,
                "title": apt.title,
                "description": apt.description,
                "scheduled_datetime": apt.scheduled_datetime,
                "duration_minutes": apt.duration_minutes,
                "timezone": apt.timezone,
                "status": apt.status.value,
                "notes": apt.notes,
                "contact": {
                    "id": apt.contact.id,
                    "name": apt.contact.name,
                    "phone_number": apt.contact.phone_number
                } if apt.contact else None,
                "agent_profile": {
                    "id": apt.agent_profile.id,
                    "name": apt.agent_profile.name
                } if apt.agent_profile else None,
                "call_log_id": apt.call_log_id,
                "reminders_count": len(apt.reminders) if apt.reminders else 0,
                "created_at": apt.created_at,
                "updated_at": apt.updated_at,
                "cancelled_at": apt.cancelled_at
            })
        
        return result
        
    finally:
        db.close()


def get_appointment_detail(appointment_id: int):
    """
    Obtiene el detalle completo de una cita incluyendo recordatorios.
    
    Args:
        appointment_id: ID de la cita
    
    Returns:
        Diccionario con toda la información de la cita
    """
    db = SessionLocal()
    try:
        appointment = db.query(Appointment).options(
            joinedload(Appointment.contact),
            joinedload(Appointment.agent_profile),
            joinedload(Appointment.call_log),
            joinedload(Appointment.reminders)
        ).filter(Appointment.id == appointment_id).first()
        
        if not appointment:
            return None
        
        return {
            "id": appointment.id,
            "company_id": appointment.company_id,
            "title": appointment.title,
            "description": appointment.description,
            "scheduled_datetime": appointment.scheduled_datetime,
            "duration_minutes": appointment.duration_minutes,
            "timezone": appointment.timezone,
            "status": appointment.status.value,
            "notes": appointment.notes,
            "contact": {
                "id": appointment.contact.id,
                "name": appointment.contact.name,
                "phone_number": appointment.contact.phone_number,
                "email": appointment.contact.email
            } if appointment.contact else None,
            "agent_profile": {
                "id": appointment.agent_profile.id,
                "name": appointment.agent_profile.name,
                "voice": appointment.agent_profile.voice
            } if appointment.agent_profile else None,
            "call_log": {
                "id": appointment.call_log.id,
                "call_sid": appointment.call_log.call_sid,
                "status": appointment.call_log.status.value,
                "duration_seconds": appointment.call_log.duration_seconds
            } if appointment.call_log else None,
            "reminders": [
                {
                    "id": reminder.id,
                    "reminder_type": reminder.reminder_type.value,
                    "time_before_minutes": reminder.time_before_minutes,
                    "reminder_datetime": reminder.reminder_datetime,
                    "status": reminder.status.value,
                    "sent_at": reminder.sent_at,
                    "error_message": reminder.error_message
                } for reminder in appointment.reminders
            ] if appointment.reminders else [],
            "created_at": appointment.created_at,
            "updated_at": appointment.updated_at,
            "cancelled_at": appointment.cancelled_at
        }
        
    finally:
        db.close()


def update_appointment(
    appointment_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    scheduled_datetime: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
    agent_profile_id: Optional[int] = None,
    notes: Optional[str] = None,
    appointment_timezone: Optional[str] = None
):
    """
    Actualiza una cita existente.
    
    Args:
        appointment_id: ID de la cita
        title: Nuevo título
        description: Nueva descripción
        scheduled_datetime: Nueva fecha/hora
        duration_minutes: Nueva duración
        agent_profile_id: Nuevo agente
        notes: Nuevas notas
        appointment_timezone: Nueva zona horaria
    
    Returns:
        Appointment actualizado
    """
    db = SessionLocal()
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        
        if not appointment:
            raise ValueError(f"Cita {appointment_id} no encontrada")
        
        # Actualizar campos si se proporcionan
        if title is not None:
            appointment.title = title
        
        if description is not None:
            appointment.description = description
        
        if scheduled_datetime is not None:
            # Manejar zona horaria
            tz = appointment_timezone or appointment.timezone or "UTC"
            
            if scheduled_datetime.tzinfo is None:
                local_tz = pytz.timezone(tz)
                scheduled_datetime = local_tz.localize(scheduled_datetime)
            
            appointment.scheduled_datetime = scheduled_datetime.astimezone(pytz.UTC)
        
        if duration_minutes is not None:
            appointment.duration_minutes = duration_minutes
        
        if agent_profile_id is not None:
            appointment.agent_profile_id = agent_profile_id
        
        if notes is not None:
            appointment.notes = notes
        
        if appointment_timezone is not None:
            appointment.timezone = appointment_timezone
        
        appointment.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(appointment)
        
        return appointment
        
    finally:
        db.close()


def cancel_appointment(appointment_id: int):
    """
    Cancela una cita.
    
    Args:
        appointment_id: ID de la cita
    
    Returns:
        Appointment cancelado
    """
    db = SessionLocal()
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        
        if not appointment:
            raise ValueError(f"Cita {appointment_id} no encontrada")
        
        appointment.status = AppointmentStatus.cancelled
        appointment.cancelled_at = datetime.now(timezone.utc)
        appointment.updated_at = datetime.now(timezone.utc)
        
        # Cancelar todos los recordatorios pendientes
        db.query(AppointmentReminder).filter(
            AppointmentReminder.appointment_id == appointment_id,
            AppointmentReminder.status == ReminderStatus.pending
        ).update({"status": ReminderStatus.cancelled})
        
        db.commit()
        db.refresh(appointment)
        
        return appointment
        
    finally:
        db.close()


def mark_appointment_completed(appointment_id: int, call_log_id: Optional[int] = None):
    """
    Marca una cita como completada.
    
    Args:
        appointment_id: ID de la cita
        call_log_id: ID del call log asociado (opcional)
    
    Returns:
        Appointment completado
    """
    db = SessionLocal()
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        
        if not appointment:
            raise ValueError(f"Cita {appointment_id} no encontrada")
        
        appointment.status = AppointmentStatus.completed
        appointment.updated_at = datetime.now(timezone.utc)
        
        if call_log_id:
            appointment.call_log_id = call_log_id
        
        db.commit()
        db.refresh(appointment)
        
        return appointment
        
    finally:
        db.close()


def get_appointments_by_month(company_id: int, year: int, month: int):
    """
    Obtiene todas las citas de un mes específico para una empresa.
    Útil para renderizar un calendario mensual en el frontend.
    
    Args:
        company_id: ID de la empresa
        year: Año (ej: 2025)
        month: Mes (1-12)
    
    Returns:
        Lista de citas del mes agrupadas por día
    """
    db = SessionLocal()
    try:
        # Crear rango de fechas para el mes
        start_date = datetime(year, month, 1, tzinfo=pytz.UTC)
        
        # Calcular el último día del mes
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=pytz.UTC)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=pytz.UTC)
        
        # Consultar citas del mes
        appointments = db.query(Appointment).filter(
            Appointment.company_id == company_id,
            Appointment.scheduled_datetime >= start_date,
            Appointment.scheduled_datetime < end_date
        ).options(
            joinedload(Appointment.contact),
            joinedload(Appointment.agent_profile)
        ).order_by(Appointment.scheduled_datetime).all()
        
        # Agrupar por día
        appointments_by_day = {}
        
        for apt in appointments:
            # Convertir a zona horaria local para agrupar por día
            tz = pytz.timezone(apt.timezone) if apt.timezone else pytz.UTC
            local_datetime = apt.scheduled_datetime.astimezone(tz)
            day_key = local_datetime.strftime("%Y-%m-%d")
            
            if day_key not in appointments_by_day:
                appointments_by_day[day_key] = []
            
            appointments_by_day[day_key].append({
                "id": apt.id,
                "title": apt.title,
                "scheduled_datetime": apt.scheduled_datetime,
                "local_time": local_datetime.strftime("%H:%M"),
                "duration_minutes": apt.duration_minutes,
                "status": apt.status.value,
                "contact_name": apt.contact.name if apt.contact else None,
                "contact_phone": apt.contact.phone_number if apt.contact else None
            })
        
        return appointments_by_day
        
    finally:
        db.close()


def get_upcoming_appointments(company_id: int, limit: int = 10):
    """
    Obtiene las próximas citas programadas de una empresa.
    Útil para mostrar en un dashboard.
    
    Args:
        company_id: ID de la empresa
        limit: Número máximo de citas a retornar
    
    Returns:
        Lista de próximas citas
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        appointments = db.query(Appointment).filter(
            Appointment.company_id == company_id,
            Appointment.scheduled_datetime >= now,
            Appointment.status == AppointmentStatus.scheduled
        ).options(
            joinedload(Appointment.contact),
            joinedload(Appointment.agent_profile)
        ).order_by(Appointment.scheduled_datetime).limit(limit).all()
        
        result = []
        for apt in appointments:
            # Calcular tiempo restante
            time_until = apt.scheduled_datetime - now
            hours_until = int(time_until.total_seconds() / 3600)
            
            result.append({
                "id": apt.id,
                "title": apt.title,
                "scheduled_datetime": apt.scheduled_datetime,
                "duration_minutes": apt.duration_minutes,
                "hours_until": hours_until,
                "contact": {
                    "id": apt.contact.id,
                    "name": apt.contact.name,
                    "phone_number": apt.contact.phone_number
                } if apt.contact else None,
                "agent_profile_name": apt.agent_profile.name if apt.agent_profile else None
            })
        
        return result
        
    finally:
        db.close()
