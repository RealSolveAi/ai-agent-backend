-- Script SQL para crear las tablas de appointments y appointment_reminders
-- Ejecutar con: psql -U postgres -d realsolveai -f migrate_appointments.sql
-- O desde Python: python run_sql_migration.py

-- Crear tabla de appointments
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    agent_profile_id INTEGER REFERENCES agent_profiles(id) ON DELETE SET NULL,
    call_log_id INTEGER REFERENCES call_logs(id) ON DELETE SET NULL,
    
    -- Información de la cita
    title VARCHAR(255) NOT NULL,
    description TEXT,
    scheduled_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    timezone VARCHAR(50),
    
    -- Estado
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    notes TEXT,
    
    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT chk_appointment_status CHECK (status IN ('scheduled', 'reminded', 'in_progress', 'completed', 'cancelled', 'missed'))
);

-- Crear índices para appointments
CREATE INDEX IF NOT EXISTS idx_appointments_company_id ON appointments(company_id);
CREATE INDEX IF NOT EXISTS idx_appointments_contact_id ON appointments(contact_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled_datetime ON appointments(scheduled_datetime);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);

-- Crear tabla de appointment_reminders
CREATE TABLE IF NOT EXISTS appointment_reminders (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    
    -- Configuración del recordatorio
    reminder_type VARCHAR(20) NOT NULL DEFAULT 'notification',
    time_before_minutes INTEGER NOT NULL,
    reminder_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Estado
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    
    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_reminder_type CHECK (reminder_type IN ('notification', 'call', 'both')),
    CONSTRAINT chk_reminder_status CHECK (status IN ('pending', 'sent', 'failed', 'cancelled'))
);

-- Crear índices para appointment_reminders
CREATE INDEX IF NOT EXISTS idx_appointment_reminders_appointment_id ON appointment_reminders(appointment_id);
CREATE INDEX IF NOT EXISTS idx_appointment_reminders_reminder_datetime ON appointment_reminders(reminder_datetime);
CREATE INDEX IF NOT EXISTS idx_appointment_reminders_status ON appointment_reminders(status);

-- Mostrar confirmación
SELECT 'Tablas de appointments creadas exitosamente!' AS mensaje;
