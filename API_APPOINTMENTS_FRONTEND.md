# 📅 API de Calendario de Citas - Guía para Frontend

## 🔗 URL Base
```
http://localhost:5050
```

## 🔐 Autenticación

Todos los endpoints requieren autenticación mediante JWT Bearer Token.

```javascript
headers: {
  'Authorization': 'Bearer YOUR_JWT_TOKEN',
  'Content-Type': 'application/json'
}
```

---

## 📋 Endpoints Disponibles

### 1. Crear Cita

**`POST /appointments`**

Crea una nueva cita programada.

**Request Body:**
```json
{
  "contact_id": 1,
  "title": "Recordatorio de pago mensual",
  "description": "Llamar para recordar el pago de la factura",
  "scheduled_datetime": "2025-01-15T10:00:00",
  "duration_minutes": 30,
  "agent_profile_id": 1,
  "timezone": "America/Bogota"
}
```

**Campos:**
- `contact_id` (requerido): ID del contacto
- `title` (requerido): Título de la cita
- `scheduled_datetime` (requerido): Fecha/hora en formato ISO 8601
- `description` (opcional): Descripción detallada
- `duration_minutes` (opcional, default: 30): Duración en minutos
- `agent_profile_id` (opcional): ID del agente (si no se especifica, usa el activo)
- `timezone` (opcional): Zona horaria (si no se especifica, usa la de la empresa)

**Response:**
```json
{
  "message": "Cita creada exitosamente",
  "appointment_id": 1,
  "scheduled_datetime": "2025-01-15T15:00:00Z",
  "timezone": "America/Bogota"
}
```

**Ejemplo con Fetch:**
```javascript
const createAppointment = async (appointmentData) => {
  const response = await fetch('http://localhost:5050/appointments', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(appointmentData)
  });
  return await response.json();
};
```

---

### 2. Listar Citas

**`GET /appointments`**

Obtiene todas las citas con filtros opcionales.

**Query Parameters:**
- `limit` (opcional, default: 50, max: 100): Número de resultados
- `offset` (opcional, default: 0): Para paginación
- `status` (opcional): Filtrar por estado (`scheduled`, `completed`, `cancelled`, etc.)
- `contact_id` (opcional): Filtrar por contacto
- `start_date` (opcional): Fecha inicio en ISO 8601 UTC
- `end_date` (opcional): Fecha fin en ISO 8601 UTC

**Ejemplo URL:**
```
GET /appointments?limit=20&status=scheduled&start_date=2025-01-01T00:00:00Z
```

**Response:**
```json
{
  "appointments": [
    {
      "id": 1,
      "title": "Recordatorio de pago mensual",
      "description": "Llamar para recordar el pago",
      "scheduled_datetime": "2025-01-15T15:00:00Z",
      "duration_minutes": 30,
      "timezone": "America/Bogota",
      "status": "scheduled",
      "notes": null,
      "contact": {
        "id": 1,
        "name": "Juan Pérez",
        "phone_number": "+573001234567"
      },
      "agent_profile": {
        "id": 1,
        "name": "Lina"
      },
      "call_log_id": null,
      "reminders_count": 2,
      "created_at": "2025-01-10T12:00:00Z",
      "updated_at": null,
      "cancelled_at": null
    }
  ],
  "count": 1
}
```

**Ejemplo con Axios:**
```javascript
const getAppointments = async (filters = {}) => {
  const params = new URLSearchParams(filters);
  const response = await axios.get(
    `http://localhost:5050/appointments?${params}`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );
  return response.data;
};

// Uso
const appointments = await getAppointments({
  status: 'scheduled',
  limit: 20
});
```

---

### 3. Próximas Citas (Dashboard)

**`GET /appointments/upcoming`**

Obtiene las próximas citas programadas (útil para dashboard).

**Query Parameters:**
- `limit` (opcional, default: 10, max: 50): Número de citas

**Response:**
```json
{
  "upcoming_appointments": [
    {
      "id": 1,
      "title": "Recordatorio de pago mensual",
      "scheduled_datetime": "2025-01-15T15:00:00Z",
      "duration_minutes": 30,
      "hours_until": 120,
      "contact": {
        "id": 1,
        "name": "Juan Pérez",
        "phone_number": "+573001234567"
      },
      "agent_profile_name": "Lina"
    }
  ],
  "count": 1
}
```

**Ejemplo React:**
```javascript
const UpcomingAppointments = () => {
  const [appointments, setAppointments] = useState([]);

  useEffect(() => {
    const fetchUpcoming = async () => {
      const response = await fetch(
        'http://localhost:5050/appointments/upcoming?limit=5',
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      const data = await response.json();
      setAppointments(data.upcoming_appointments);
    };
    fetchUpcoming();
  }, []);

  return (
    <div>
      {appointments.map(apt => (
        <div key={apt.id}>
          <h3>{apt.title}</h3>
          <p>En {apt.hours_until} horas</p>
          <p>Contacto: {apt.contact.name}</p>
        </div>
      ))}
    </div>
  );
};
```

---

### 4. Vista de Calendario Mensual

**`GET /appointments/calendar/{year}/{month}`**

Obtiene todas las citas de un mes agrupadas por día (perfecto para renderizar calendarios).

**Path Parameters:**
- `year`: Año (ej: 2025)
- `month`: Mes (1-12)

**Ejemplo URL:**
```
GET /appointments/calendar/2025/1
```

**Response:**
```json
{
  "year": 2025,
  "month": 1,
  "appointments_by_day": {
    "2025-01-15": [
      {
        "id": 1,
        "title": "Recordatorio de pago mensual",
        "scheduled_datetime": "2025-01-15T15:00:00Z",
        "local_time": "10:00",
        "duration_minutes": 30,
        "status": "scheduled",
        "contact_name": "Juan Pérez",
        "contact_phone": "+573001234567"
      },
      {
        "id": 2,
        "title": "Seguimiento cliente",
        "scheduled_datetime": "2025-01-15T18:00:00Z",
        "local_time": "13:00",
        "duration_minutes": 15,
        "status": "scheduled",
        "contact_name": "María García",
        "contact_phone": "+573007654321"
      }
    ],
    "2025-01-20": [
      {
        "id": 3,
        "title": "Recordatorio de cita médica",
        "scheduled_datetime": "2025-01-20T14:00:00Z",
        "local_time": "09:00",
        "duration_minutes": 30,
        "status": "scheduled",
        "contact_name": "Carlos López",
        "contact_phone": "+573009876543"
      }
    ]
  }
}
```

**Ejemplo React Calendar:**
```javascript
const CalendarView = () => {
  const [calendarData, setCalendarData] = useState({});
  const [currentDate, setCurrentDate] = useState(new Date());

  const fetchCalendar = async (year, month) => {
    const response = await fetch(
      `http://localhost:5050/appointments/calendar/${year}/${month}`,
      {
        headers: { 'Authorization': `Bearer ${token}` }
      }
    );
    const data = await response.json();
    setCalendarData(data.appointments_by_day);
  };

  useEffect(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    fetchCalendar(year, month);
  }, [currentDate]);

  return (
    <div className="calendar">
      {/* Renderizar días del mes */}
      {Object.entries(calendarData).map(([date, appointments]) => (
        <div key={date} className="calendar-day">
          <div className="date">{date}</div>
          <div className="appointments">
            {appointments.map(apt => (
              <div key={apt.id} className="appointment-item">
                <span>{apt.local_time}</span>
                <span>{apt.title}</span>
                <span>{apt.contact_name}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
```

---

### 5. Detalle de Cita

**`GET /appointments/{appointment_id}`**

Obtiene el detalle completo de una cita incluyendo recordatorios.

**Response:**
```json
{
  "id": 1,
  "company_id": 1,
  "title": "Recordatorio de pago mensual",
  "description": "Llamar para recordar el pago de la factura",
  "scheduled_datetime": "2025-01-15T15:00:00Z",
  "duration_minutes": 30,
  "timezone": "America/Bogota",
  "status": "scheduled",
  "notes": null,
  "contact": {
    "id": 1,
    "name": "Juan Pérez",
    "phone_number": "+573001234567",
    "email": "juan@example.com"
  },
  "agent_profile": {
    "id": 1,
    "name": "Lina",
    "voice": "coral"
  },
  "call_log": null,
  "reminders": [
    {
      "id": 1,
      "reminder_type": "call",
      "time_before_minutes": 1440,
      "reminder_datetime": "2025-01-14T15:00:00Z",
      "status": "pending",
      "sent_at": null,
      "error_message": null
    }
  ],
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": null,
  "cancelled_at": null
}
```

---

### 6. Actualizar Cita

**`PUT /appointments/{appointment_id}`**

Actualiza una cita existente. Todos los campos son opcionales.

**Request Body:**
```json
{
  "title": "Nuevo título",
  "scheduled_datetime": "2025-01-15T11:00:00",
  "notes": "Cliente confirmó asistencia por WhatsApp"
}
```

**Response:**
```json
{
  "message": "Cita actualizada exitosamente",
  "appointment_id": 1
}
```

---

### 7. Cancelar Cita

**`DELETE /appointments/{appointment_id}`**

Cancela una cita (no la elimina, solo cambia el estado a `cancelled`).

**Response:**
```json
{
  "message": "Cita cancelada exitosamente",
  "appointment_id": 1,
  "cancelled_at": "2025-01-10T14:30:00Z"
}
```

---

### 8. Agregar Recordatorio

**`POST /appointments/{appointment_id}/reminders`**

Agrega un recordatorio a una cita.

**Request Body:**
```json
{
  "reminder_type": "call",
  "time_before_minutes": 1440
}
```

**Tipos de recordatorio:**
- `"notification"`: Solo registro interno
- `"call"`: Llamada automática al contacto
- `"both"`: Notificación + Llamada

**Ejemplos de `time_before_minutes`:**
- `60` = 1 hora antes
- `1440` = 1 día antes (24 horas)
- `2880` = 2 días antes
- `10080` = 1 semana antes (7 días)

**Response:**
```json
{
  "message": "Recordatorio creado exitosamente",
  "reminder_id": 1,
  "reminder_datetime": "2025-01-14T15:00:00Z",
  "reminder_type": "call"
}
```

**Ejemplo React:**
```javascript
const addReminder = async (appointmentId, reminderData) => {
  const response = await fetch(
    `http://localhost:5050/appointments/${appointmentId}/reminders`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(reminderData)
    }
  );
  return await response.json();
};

// Uso: Agregar recordatorio de 1 día antes con llamada
await addReminder(1, {
  reminder_type: 'call',
  time_before_minutes: 1440
});
```

---

### 9. Eliminar Recordatorio

**`DELETE /appointments/{appointment_id}/reminders/{reminder_id}`**

Elimina un recordatorio específico.

**Response:**
```json
{
  "message": "Recordatorio eliminado exitosamente",
  "reminder_id": 1
}
```

---

### 10. Iniciar Llamada Manual

**`POST /appointments/{appointment_id}/call`**

Inicia una llamada inmediata para una cita (sin esperar al recordatorio programado).

**Response:**
```json
{
  "message": "Llamada iniciada exitosamente",
  "call_sid": "CA1234567890abcdef",
  "to": "+573001234567",
  "contact_name": "Juan Pérez"
}
```

**Ejemplo:**
```javascript
const callNow = async (appointmentId) => {
  const response = await fetch(
    `http://localhost:5050/appointments/${appointmentId}/call`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  return await response.json();
};
```

---

## 🎨 Ejemplo Completo: Componente de Calendario

```javascript
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:5050';

const AppointmentCalendar = ({ token }) => {
  const [appointments, setAppointments] = useState({});
  const [currentDate, setCurrentDate] = useState(new Date());
  const [loading, setLoading] = useState(false);

  // Cargar citas del mes
  const loadMonthAppointments = async (year, month) => {
    setLoading(true);
    try {
      const response = await axios.get(
        `${API_BASE}/appointments/calendar/${year}/${month}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      setAppointments(response.data.appointments_by_day);
    } catch (error) {
      console.error('Error cargando citas:', error);
    } finally {
      setLoading(false);
    }
  };

  // Crear nueva cita
  const createAppointment = async (appointmentData) => {
    try {
      const response = await axios.post(
        `${API_BASE}/appointments`,
        appointmentData,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      // Recargar calendario
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth() + 1;
      await loadMonthAppointments(year, month);
      
      return response.data;
    } catch (error) {
      console.error('Error creando cita:', error);
      throw error;
    }
  };

  // Agregar recordatorio
  const addReminder = async (appointmentId, reminderType, minutesBefore) => {
    try {
      await axios.post(
        `${API_BASE}/appointments/${appointmentId}/reminders`,
        {
          reminder_type: reminderType,
          time_before_minutes: minutesBefore
        },
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
    } catch (error) {
      console.error('Error agregando recordatorio:', error);
      throw error;
    }
  };

  useEffect(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    loadMonthAppointments(year, month);
  }, [currentDate]);

  return (
    <div className="appointment-calendar">
      {/* Navegación de mes */}
      <div className="calendar-header">
        <button onClick={() => {
          const newDate = new Date(currentDate);
          newDate.setMonth(newDate.getMonth() - 1);
          setCurrentDate(newDate);
        }}>
          ← Anterior
        </button>
        <h2>
          {currentDate.toLocaleDateString('es-ES', { 
            month: 'long', 
            year: 'numeric' 
          })}
        </h2>
        <button onClick={() => {
          const newDate = new Date(currentDate);
          newDate.setMonth(newDate.getMonth() + 1);
          setCurrentDate(newDate);
        }}>
          Siguiente →
        </button>
      </div>

      {/* Grid de calendario */}
      {loading ? (
        <div>Cargando...</div>
      ) : (
        <div className="calendar-grid">
          {Object.entries(appointments).map(([date, dayAppointments]) => (
            <div key={date} className="calendar-day">
              <div className="date-header">{date}</div>
              <div className="appointments-list">
                {dayAppointments.map(apt => (
                  <div key={apt.id} className="appointment-card">
                    <span className="time">{apt.local_time}</span>
                    <span className="title">{apt.title}</span>
                    <span className="contact">{apt.contact_name}</span>
                    <span className={`status ${apt.status}`}>
                      {apt.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AppointmentCalendar;
```

---

## 📊 Estados de Citas

Las citas pueden tener los siguientes estados:

- `scheduled`: Programada (inicial)
- `reminded`: Recordatorio enviado
- `in_progress`: Llamada en curso
- `completed`: Completada exitosamente
- `cancelled`: Cancelada
- `missed`: No se realizó

---

## 🌍 Manejo de Zonas Horarias

**Importante:** 
- Todas las fechas se guardan en **UTC** en el backend
- El campo `timezone` indica la zona horaria local
- El campo `local_time` en las respuestas de calendario ya está convertido

**Ejemplo:**
```javascript
// Crear cita para las 10:00 AM hora de Bogotá
const appointment = {
  contact_id: 1,
  title: "Recordatorio",
  scheduled_datetime: "2025-01-15T10:00:00", // Hora local
  timezone: "America/Bogota"
};

// El backend lo guardará como:
// scheduled_datetime: "2025-01-15T15:00:00Z" (UTC)
```

---

## 🔔 Tipos de Recordatorios

### 1. Notification (Solo registro)
```json
{
  "reminder_type": "notification",
  "time_before_minutes": 60
}
```
Solo actualiza el estado interno. No hace llamada.

### 2. Call (Llamada automática)
```json
{
  "reminder_type": "call",
  "time_before_minutes": 1440
}
```
Realiza una llamada automática al contacto.

### 3. Both (Ambos)
```json
{
  "reminder_type": "both",
  "time_before_minutes": 2880
}
```
Actualiza estado Y realiza llamada.

---

## 🚀 Flujo Completo de Uso

### 1. Crear Cita
```javascript
const newAppointment = await createAppointment({
  contact_id: 1,
  title: "Recordatorio de pago",
  scheduled_datetime: "2025-01-15T10:00:00",
  timezone: "America/Bogota"
});
```

### 2. Agregar Recordatorios
```javascript
// Recordatorio 1 día antes
await addReminder(newAppointment.appointment_id, {
  reminder_type: "call",
  time_before_minutes: 1440
});

// Recordatorio 1 hora antes
await addReminder(newAppointment.appointment_id, {
  reminder_type: "notification",
  time_before_minutes: 60
});
```

### 3. Ver en Calendario
```javascript
const calendarData = await getCalendarMonth(2025, 1);
// Renderizar en tu componente de calendario
```

### 4. Llamar Manualmente (opcional)
```javascript
await callAppointmentNow(appointmentId);
```

---

## 📝 Notas Importantes

1. **Autenticación**: Todos los endpoints requieren JWT token
2. **Zona Horaria**: Siempre especifica la zona horaria correcta
3. **Paginación**: Usa `limit` y `offset` para grandes volúmenes
4. **Estados**: Monitorea el campo `status` para actualizar la UI
5. **Recordatorios**: Se ejecutan automáticamente en el backend
6. **Llamadas**: El sistema inicia llamadas automáticas según los recordatorios

---

## 🐛 Manejo de Errores

```javascript
try {
  const appointment = await createAppointment(data);
} catch (error) {
  if (error.response) {
    // Error del servidor
    console.error('Error:', error.response.data.detail);
    // Mostrar mensaje al usuario
  } else {
    // Error de red
    console.error('Error de conexión');
  }
}
```

---

## 📚 Recursos Adicionales

- **Documentación Interactiva**: http://localhost:5050/docs
- **Swagger UI**: Prueba todos los endpoints directamente desde el navegador
- **Redoc**: http://localhost:5050/redoc (documentación alternativa)

---

¿Necesitas ayuda? Contacta al equipo de backend. 🚀
