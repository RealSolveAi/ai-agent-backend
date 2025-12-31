# Importar todos los modelos para que SQLAlchemy pueda resolver las relaciones
# Este archivo asegura que todos los modelos estén disponibles cuando SQLAlchemy
# intente resolver las relaciones por nombre de string (ej: "AgentProfile", "Company")

from app.models.company import Company
from app.models.user import User
from app.models.company_phone_number import CompanyPhoneNumber
from app.models.call_log import CallLog
from app.models.call_turn import CallTurn
from app.models.contact import Contact
from app.models.agent_profile import AgentProfile
from app.models.appointment import Appointment
from app.models.appointment_reminder import AppointmentReminder

# Exportar todos los modelos
__all__ = [
    "Company",
    "User",
    "CompanyPhoneNumber",
    "CallLog",
    "CallTurn",
    "Contact",
    "AgentProfile",
    "Appointment",
    "AppointmentReminder",
]
