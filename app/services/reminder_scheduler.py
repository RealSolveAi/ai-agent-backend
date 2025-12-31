# app/services/reminder_scheduler.py
"""
Servicio para programar y ejecutar recordatorios de citas usando APScheduler.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from app.persistance.db import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.appointment_reminder import AppointmentReminder, ReminderType, ReminderStatus
from app.models.contact import Contact
from app.models.agent_profile import AgentProfile
import logging

logger = logging.getLogger(__name__)

# Scheduler global
scheduler = BackgroundScheduler()


def start_scheduler():
    """Inicia el scheduler de recordatorios."""
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ Scheduler de recordatorios iniciado")
        
        # Cargar recordatorios pendientes al iniciar
        load_pending_reminders()


def stop_scheduler():
    """Detiene el scheduler de recordatorios."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("❌ Scheduler de recordatorios detenido")


def load_pending_reminders():
    """
    Carga todos los recordatorios pendientes al iniciar el servidor.
    Esto asegura que los recordatorios programados se mantengan después de reiniciar.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        # Obtener recordatorios pendientes que aún no han pasado
        pending_reminders = db.query(AppointmentReminder).filter(
            AppointmentReminder.status == ReminderStatus.pending,
            AppointmentReminder.reminder_datetime > now
        ).all()
        
        logger.info(f"📋 Cargando {len(pending_reminders)} recordatorios pendientes...")
        
        for reminder in pending_reminders:
            schedule_reminder_job(reminder.id, reminder.reminder_datetime)
        
        logger.info(f"✅ {len(pending_reminders)} recordatorios programados")
        
    except Exception as e:
        logger.error(f"❌ Error cargando recordatorios pendientes: {str(e)}")
    finally:
        db.close()


def create_reminder(
    appointment_id: int,
    reminder_type: ReminderType,
    time_before_minutes: int
):
    """
    Crea un recordatorio para una cita.
    
    Args:
        appointment_id: ID de la cita
        reminder_type: Tipo de recordatorio (notification, call, both)
        time_before_minutes: Minutos antes de la cita para ejecutar el recordatorio
    
    Returns:
        AppointmentReminder creado
    """
    db = SessionLocal()
    try:
        # Obtener la cita
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        
        if not appointment:
            raise ValueError(f"Cita {appointment_id} no encontrada")
        
        # Calcular la fecha/hora del recordatorio
        reminder_datetime = appointment.scheduled_datetime - timedelta(minutes=time_before_minutes)
        
        # Validar que el recordatorio no sea en el pasado
        now = datetime.now(timezone.utc)
        if reminder_datetime < now:
            raise ValueError("El recordatorio no puede ser en el pasado")
        
        # Crear el recordatorio
        reminder = AppointmentReminder(
            appointment_id=appointment_id,
            reminder_type=reminder_type,
            time_before_minutes=time_before_minutes,
            reminder_datetime=reminder_datetime,
            status=ReminderStatus.pending
        )
        
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        
        # Programar el job en APScheduler
        schedule_reminder_job(reminder.id, reminder_datetime)
        
        logger.info(f"✅ Recordatorio {reminder.id} creado para cita {appointment_id}")
        
        return reminder
        
    finally:
        db.close()


def schedule_reminder_job(reminder_id: int, reminder_datetime: datetime):
    """
    Programa un job en APScheduler para ejecutar un recordatorio.
    
    Args:
        reminder_id: ID del recordatorio
        reminder_datetime: Fecha/hora para ejecutar el recordatorio (UTC)
    """
    job_id = f"reminder_{reminder_id}"
    
    # Verificar si ya existe un job con este ID
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        logger.warning(f"⚠️  Job {job_id} ya existe, reemplazando...")
        scheduler.remove_job(job_id)
    
    # Programar el job
    scheduler.add_job(
        func=execute_reminder,
        trigger=DateTrigger(run_date=reminder_datetime),
        args=[reminder_id],
        id=job_id,
        name=f"Recordatorio {reminder_id}",
        replace_existing=True
    )
    
    logger.info(f"📅 Job programado: {job_id} para {reminder_datetime}")


def execute_reminder(reminder_id: int):
    """
    Ejecuta un recordatorio: envía notificación y/o realiza llamada.
    
    Args:
        reminder_id: ID del recordatorio a ejecutar
    """
    db = SessionLocal()
    try:
        # Obtener el recordatorio con la cita relacionada
        reminder = db.query(AppointmentReminder).options(
            joinedload(AppointmentReminder.appointment).joinedload(Appointment.contact),
            joinedload(AppointmentReminder.appointment).joinedload(Appointment.agent_profile)
        ).filter(AppointmentReminder.id == reminder_id).first()
        
        if not reminder:
            logger.error(f"❌ Recordatorio {reminder_id} no encontrado")
            return
        
        appointment = reminder.appointment
        
        # Verificar que la cita no esté cancelada
        if appointment.status == AppointmentStatus.cancelled:
            logger.info(f"⚠️  Cita {appointment.id} cancelada, omitiendo recordatorio {reminder_id}")
            reminder.status = ReminderStatus.cancelled
            db.commit()
            return
        
        logger.info(f"🔔 Ejecutando recordatorio {reminder_id} para cita {appointment.id}")
        
        try:
            # Ejecutar según el tipo de recordatorio
            if reminder.reminder_type in [ReminderType.notification, ReminderType.both]:
                # Crear notificación interna (simplemente actualizar estado)
                logger.info(f"📢 Notificación enviada para cita: {appointment.title}")
                
                # Actualizar estado de la cita a "reminded"
                if appointment.status == AppointmentStatus.scheduled:
                    appointment.status = AppointmentStatus.reminded
            
            if reminder.reminder_type in [ReminderType.call, ReminderType.both]:
                # Realizar llamada automática
                logger.info(f"📞 Iniciando llamada de recordatorio para: {appointment.contact.name}")
                
                # Importar aquí para evitar circular import
                from app.services.twilio_service import make_call_internal
                
                # Realizar la llamada
                try:
                    call_result = make_call_internal(
                        to_phone_number=appointment.contact.phone_number,
                        company_id=appointment.company_id,
                        contact_id=appointment.contact_id,
                        agent_profile_id=appointment.agent_profile_id,
                        appointment_id=appointment.id
                    )
                    
                    logger.info(f"✅ Llamada de recordatorio iniciada: {call_result.get('call_sid')}")
                    
                except Exception as call_error:
                    logger.error(f"❌ Error al realizar llamada de recordatorio: {str(call_error)}")
                    raise call_error
            
            # Marcar recordatorio como enviado
            reminder.status = ReminderStatus.sent
            reminder.sent_at = datetime.now(timezone.utc)
            
            db.commit()
            
            logger.info(f"✅ Recordatorio {reminder_id} ejecutado exitosamente")
            
        except Exception as e:
            # Marcar recordatorio como fallido
            reminder.status = ReminderStatus.failed
            reminder.error_message = str(e)
            db.commit()
            
            logger.error(f"❌ Error ejecutando recordatorio {reminder_id}: {str(e)}")
            raise
        
    except Exception as e:
        logger.error(f"❌ Error en execute_reminder: {str(e)}")
    finally:
        db.close()


def cancel_reminder(reminder_id: int):
    """
    Cancela un recordatorio programado.
    
    Args:
        reminder_id: ID del recordatorio
    """
    db = SessionLocal()
    try:
        reminder = db.query(AppointmentReminder).filter(AppointmentReminder.id == reminder_id).first()
        
        if not reminder:
            raise ValueError(f"Recordatorio {reminder_id} no encontrado")
        
        # Cancelar el job en APScheduler
        job_id = f"reminder_{reminder_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"🗑️  Job {job_id} eliminado del scheduler")
        
        # Actualizar estado en la base de datos
        reminder.status = ReminderStatus.cancelled
        db.commit()
        
        logger.info(f"❌ Recordatorio {reminder_id} cancelado")
        
        return reminder
        
    finally:
        db.close()


def reschedule_appointment_reminders(appointment_id: int):
    """
    Reprograma todos los recordatorios de una cita cuando se actualiza la fecha/hora.
    
    Args:
        appointment_id: ID de la cita
    """
    db = SessionLocal()
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        
        if not appointment:
            raise ValueError(f"Cita {appointment_id} no encontrada")
        
        # Obtener todos los recordatorios pendientes
        reminders = db.query(AppointmentReminder).filter(
            AppointmentReminder.appointment_id == appointment_id,
            AppointmentReminder.status == ReminderStatus.pending
        ).all()
        
        now = datetime.now(timezone.utc)
        
        for reminder in reminders:
            # Recalcular la fecha/hora del recordatorio
            new_reminder_datetime = appointment.scheduled_datetime - timedelta(minutes=reminder.time_before_minutes)
            
            # Si el nuevo recordatorio es en el pasado, cancelarlo
            if new_reminder_datetime < now:
                logger.warning(f"⚠️  Recordatorio {reminder.id} ahora es en el pasado, cancelando...")
                reminder.status = ReminderStatus.cancelled
                
                # Eliminar job del scheduler
                job_id = f"reminder_{reminder.id}"
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
            else:
                # Actualizar fecha/hora y reprogramar
                reminder.reminder_datetime = new_reminder_datetime
                schedule_reminder_job(reminder.id, new_reminder_datetime)
                logger.info(f"🔄 Recordatorio {reminder.id} reprogramado para {new_reminder_datetime}")
        
        db.commit()
        
        logger.info(f"✅ Recordatorios de cita {appointment_id} reprogramados")
        
    finally:
        db.close()


def delete_reminder(reminder_id: int):
    """
    Elimina permanentemente un recordatorio.
    
    Args:
        reminder_id: ID del recordatorio
    """
    db = SessionLocal()
    try:
        reminder = db.query(AppointmentReminder).filter(AppointmentReminder.id == reminder_id).first()
        
        if not reminder:
            raise ValueError(f"Recordatorio {reminder_id} no encontrado")
        
        # Cancelar el job en APScheduler
        job_id = f"reminder_{reminder_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"🗑️  Job {job_id} eliminado del scheduler")
        
        # Eliminar de la base de datos
        db.delete(reminder)
        db.commit()
        
        logger.info(f"🗑️  Recordatorio {reminder_id} eliminado permanentemente")
        
    finally:
        db.close()
