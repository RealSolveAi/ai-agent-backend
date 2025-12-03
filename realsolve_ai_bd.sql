-- =======================================================
-- ENUMERACIONES
-- =======================================================
-- Nota: PostgreSQL no soporta IF NOT EXISTS para CREATE TYPE
-- Estos errores son esperados si los tipos ya existen y son manejados por init_database.py
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('superadmin', 'admin', 'agent', 'viewer');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE phone_type AS ENUM ('inbound', 'outbound', 'both');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE call_direction AS ENUM ('inbound', 'outbound');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE call_status AS ENUM ('initiated', 'in_progress', 'completed', 'no_answer', 'no_response', 'failed');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE sentiment_type AS ENUM ('positive', 'neutral', 'negative');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE appointment_status AS ENUM ('scheduled', 'completed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE campaign_status AS ENUM ('draft', 'running', 'paused', 'completed');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE interest_level AS ENUM ('low', 'medium', 'high');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- =======================================================
-- TABLA: companies
-- =======================================================
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    industry VARCHAR(100),
    country VARCHAR(100),
    timezone VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: users
-- =======================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role user_role DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    last_logout TIMESTAMP
);

-- =======================================================
-- TABLA: company_phone_numbers
-- =======================================================
CREATE TABLE IF NOT EXISTS company_phone_numbers (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    twilio_sid VARCHAR(255),
    phone_number VARCHAR(50) NOT NULL,
    friendly_name VARCHAR(100),
    country_code VARCHAR(10),
    is_active BOOLEAN DEFAULT TRUE,
    type phone_type DEFAULT 'both',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: agent_profiles
-- =======================================================
CREATE TABLE IF NOT EXISTS agent_profiles (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    voice VARCHAR(50) DEFAULT 'coral',
    temperature FLOAT DEFAULT 0.8,
    prompt TEXT,
    working_hours JSONB,
    timezone VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: integrations
-- =======================================================
CREATE TABLE IF NOT EXISTS integrations (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    platform VARCHAR(100) NOT NULL,
    api_key TEXT,
    access_token TEXT,
    refresh_token TEXT,
    connected_at TIMESTAMP,
    status VARCHAR(50)
);

-- =======================================================
-- TABLA: contacts
-- =======================================================
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100),
    phone_number VARCHAR(50),
    email VARCHAR(255),
    description TEXT,
    notes TEXT,
    preferred_call_time_start TIME,
    preferred_call_time_end TIME,
    timezone VARCHAR(50),
    tags TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction_at TIMESTAMP
);

-- =======================================================
-- TABLA: call_logs
-- =======================================================
CREATE TABLE IF NOT EXISTS call_logs (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    phone_number_id INT REFERENCES company_phone_numbers(id) ON DELETE SET NULL,
    contact_id INT REFERENCES contacts(id) ON DELETE SET NULL,
    agent_profile_id INT REFERENCES agent_profiles(id) ON DELETE SET NULL,
    call_sid VARCHAR(255) UNIQUE,
    to_phone_number VARCHAR(50),
    from_phone_number VARCHAR(50),
    direction call_direction,
    status call_status DEFAULT 'initiated',
    duration_seconds INT,
    transcription_summary TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    recording_url TEXT,
    recording_sid VARCHAR(255),
    recording_duration INT,
    customer_phone VARCHAR(50),
    customer_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: call_turns
-- =======================================================
CREATE TABLE IF NOT EXISTS call_turns (
    id SERIAL PRIMARY KEY,
    call_log_id INT REFERENCES call_logs(id) ON DELETE CASCADE,
    speaker VARCHAR(20) CHECK (speaker IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    intent VARCHAR(100),
    confidence INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    audio_segment_url TEXT,
    sentiment sentiment_type
);

-- =======================================================
-- TABLA: detected_intents
-- =======================================================
CREATE TABLE IF NOT EXISTS detected_intents (
    id SERIAL PRIMARY KEY,
    call_id INT REFERENCES call_logs(id) ON DELETE CASCADE,
    intent_name VARCHAR(100),
    confidence FLOAT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: extracted_fields
-- =======================================================
CREATE TABLE IF NOT EXISTS extracted_fields (
    id SERIAL PRIMARY KEY,
    call_id INT REFERENCES call_logs(id) ON DELETE CASCADE,
    field_name VARCHAR(100),
    field_value VARCHAR(255),
    confidence FLOAT
);

-- =======================================================
-- TABLA: recordings
-- =======================================================
CREATE TABLE IF NOT EXISTS recordings (
    id SERIAL PRIMARY KEY,
    call_id INT UNIQUE REFERENCES call_logs(id) ON DELETE CASCADE,
    url TEXT,
    transcription_url TEXT,
    file_size INT,
    format VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: appointments
-- =======================================================
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    call_id INT REFERENCES call_logs(id) ON DELETE CASCADE,
    contact_id INT REFERENCES contacts(id) ON DELETE CASCADE,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    title VARCHAR(255),
    description TEXT,
    datetime TIMESTAMP,
    status appointment_status DEFAULT 'scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: leads
-- =======================================================
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    contact_id INT REFERENCES contacts(id) ON DELETE SET NULL,
    source VARCHAR(50) CHECK (source IN ('inbound_call', 'outbound_call', 'campaign')),
    interest_level interest_level DEFAULT 'medium',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: outbound_campaigns
-- =======================================================
CREATE TABLE IF NOT EXISTS outbound_campaigns (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100),
    description TEXT,
    status campaign_status DEFAULT 'draft',
    scheduled_start TIMESTAMP,
    scheduled_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =======================================================
-- TABLA: campaign_targets
-- =======================================================
CREATE TABLE IF NOT EXISTS campaign_targets (
    id SERIAL PRIMARY KEY,
    campaign_id INT REFERENCES outbound_campaigns(id) ON DELETE CASCADE,
    contact_id INT REFERENCES contacts(id) ON DELETE CASCADE,
    call_id INT REFERENCES call_logs(id) ON DELETE SET NULL,
    status VARCHAR(50) CHECK (status IN ('pending', 'called', 'failed', 'success')) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
