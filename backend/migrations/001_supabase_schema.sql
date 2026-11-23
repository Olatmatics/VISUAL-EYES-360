-- ============================================================================
-- VISUAL EYES 360 — SUPABASE / POSTGRESQL PRODUCTION SCHEMA MIGRATION
-- Multi-station Fuel Automation, Cashless Dispensing & Forecourt Telemetry
-- ============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enums
DO $$ BEGIN
    CREATE TYPE user_role_type AS ENUM ('SUPERIOR_ADMIN', 'MANAGER', 'SPECIAL_CUSTOMER', 'SERVICE_ACCOUNT');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE fuel_type AS ENUM ('PMS', 'AGO', 'DPK');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE transaction_status AS ENUM ('PENDING', 'AUTHORIZED', 'DISPENSING', 'COMPLETED', 'INTERRUPTED_POWER', 'RECON_DISCREPANCY', 'FAILED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE payment_channel AS ENUM ('OPAY_POS', 'BANK_TRANSFER', 'RFID_WALLET', 'CASH_VOUCHER');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE alert_severity AS ENUM ('INFO', 'WARNING', 'CRITICAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ----------------------------------------------------------------------------
-- 1. Stations & Geographical Hierarchy
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(120) UNIQUE NOT NULL,
    code VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS lgas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state_id UUID NOT NULL REFERENCES states(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    UNIQUE(state_id, name)
);

CREATE TABLE IF NOT EXISTS stations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(180) NOT NULL,
    address TEXT,
    state_id UUID REFERENCES states(id),
    lga_id UUID REFERENCES lgas(id),
    city VARCHAR(120),
    gps_lat VARCHAR(30),
    gps_lng VARCHAR(30),
    contact_person VARCHAR(120),
    phone VARCHAR(40) NOT NULL,
    email VARCHAR(180),
    status VARCHAR(30) DEFAULT 'ACTIVE',
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 2. Storage Tanks & ATG Probes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fuel_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL
);

CREATE TABLE IF NOT EXISTS tanks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    product_id UUID REFERENCES fuel_products(id),
    capacity_l DECIMAL(10, 2) NOT NULL DEFAULT 50000.00,
    current_volume_l DECIMAL(10, 2) DEFAULT 0.00,
    current_level_mm DECIMAL(8, 2) DEFAULT 0.00,
    current_water_mm DECIMAL(6, 2) DEFAULT 0.00,
    current_temperature_c DECIMAL(4, 2) DEFAULT 25.00,
    hatch_open BOOLEAN DEFAULT FALSE,
    status VARCHAR(30) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(station_id, code)
);

CREATE TABLE IF NOT EXISTS tank_controllers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_uid VARCHAR(64) UNIQUE NOT NULL,
    tank_id UUID UNIQUE NOT NULL REFERENCES tanks(id) ON DELETE CASCADE,
    firmware_version VARCHAR(20) NOT NULL,
    connection_mode VARCHAR(10) CHECK (connection_mode IN ('WIFI', 'SIM')),
    signal_strength_dbm INT,
    is_online BOOLEAN DEFAULT FALSE,
    last_heartbeat TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. Dispensers, Nozzles & Dedicated ESP32-S3 FCCs
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dispensers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    manufacturer VARCHAR(80) DEFAULT 'Wayne',
    model VARCHAR(80),
    protocol VARCHAR(80) DEFAULT 'Wayne_Dart',
    interface VARCHAR(40) DEFAULT 'RS485_CurrentLoop',
    serial VARCHAR(80),
    status VARCHAR(30) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(station_id, code)
);

CREATE TABLE IF NOT EXISTS nozzles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dispenser_id UUID NOT NULL REFERENCES dispensers(id) ON DELETE CASCADE,
    tank_id UUID REFERENCES tanks(id),
    number INT NOT NULL DEFAULT 1,
    product_id UUID REFERENCES fuel_products(id),
    price DECIMAL(8, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(30) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dispenser_id, number)
);

CREATE TABLE IF NOT EXISTS fcc_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_uid VARCHAR(64) UNIQUE NOT NULL,
    nozzle_id UUID UNIQUE NOT NULL REFERENCES nozzles(id) ON DELETE CASCADE,
    firmware_version VARCHAR(20) NOT NULL,
    connection_mode VARCHAR(10) CHECK (connection_mode IN ('WIFI', 'SIM')),
    signal_strength_dbm INT,
    calibration_factor DECIMAL(8, 4) NOT NULL DEFAULT 100.0000, -- Pulses per Litre
    is_online BOOLEAN DEFAULT FALSE,
    last_heartbeat TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pos_terminals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    terminal_id VARCHAR(50) UNIQUE NOT NULL,
    serial_number VARCHAR(50) UNIQUE NOT NULL,
    provider VARCHAR(30) DEFAULT 'OPAY',
    station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    nozzle_id UUID UNIQUE REFERENCES nozzles(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 4. Special Customer RFID & Atomic Wallet Management
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(180) NOT NULL,
    phone VARCHAR(40) UNIQUE NOT NULL,
    email VARCHAR(180),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wallets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID UNIQUE NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    balance DECIMAL(12, 2) NOT NULL DEFAULT 0.00 CHECK (balance >= 0),
    reserved_balance DECIMAL(12, 2) NOT NULL DEFAULT 0.00 CHECK (reserved_balance >= 0),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rfid_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    card_uid VARCHAR(64) UNIQUE NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    auth_key_hash VARCHAR(128) NOT NULL,
    is_blocked BOOLEAN DEFAULT FALSE,
    daily_spend_limit DECIMAL(10, 2) DEFAULT 100000.00,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 5. Dual-Measurement Transactions (CPU vs Pulser 0.49L Threshold)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fuel_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_ref VARCHAR(64) UNIQUE NOT NULL,
    station_id UUID NOT NULL REFERENCES stations(id),
    nozzle_id UUID NOT NULL REFERENCES nozzles(id),
    fcc_device_id UUID NOT NULL REFERENCES fcc_devices(id),
    customer_id UUID REFERENCES customers(id),
    payment_channel payment_channel NOT NULL,
    unit_price DECIMAL(8, 2) NOT NULL,
    requested_amount DECIMAL(10, 2) NOT NULL,
    
    -- Dual Measurement Verification
    dispenser_cpu_volume DECIMAL(8, 3) NOT NULL DEFAULT 0.000,
    independent_pulser_volume DECIMAL(8, 3) NOT NULL DEFAULT 0.000,
    raw_pulse_count BIGINT NOT NULL DEFAULT 0,
    volume_difference DECIMAL(8, 3) GENERATED ALWAYS AS (abs(dispenser_cpu_volume - independent_pulser_volume)) STORED,
    discrepancy_alert BOOLEAN GENERATED ALWAYS AS (abs(dispenser_cpu_volume - independent_pulser_volume) >= 0.490) STORED,
    
    total_amount_billed DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    status transaction_status NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ----------------------------------------------------------------------------
-- 6. Alerts & Audit Trail
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id UUID REFERENCES stations(id) ON DELETE CASCADE,
    alert_type VARCHAR(60) NOT NULL,
    severity alert_severity NOT NULL DEFAULT 'INFO',
    title VARCHAR(180) NOT NULL,
    description TEXT,
    entity_type VARCHAR(50),
    entity_id VARCHAR(50),
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_by VARCHAR(80),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id VARCHAR(80) NOT NULL,
    actor_name VARCHAR(180),
    station_id UUID REFERENCES stations(id),
    action VARCHAR(60) NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id VARCHAR(60),
    changes JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 7. Supabase Row Level Security (RLS) Setup
-- ----------------------------------------------------------------------------
ALTER TABLE stations ENABLE ROW LEVEL SECURITY;
ALTER TABLE nozzles ENABLE ROW LEVEL SECURITY;
ALTER TABLE fuel_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tanks ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_alerts ENABLE ROW LEVEL SECURITY;

-- Superior Admin: Full unrestricted access
CREATE POLICY superior_admin_all ON stations
    FOR ALL
    TO authenticated
    USING (auth.jwt() ->> 'role' = 'SUPERIOR_ADMIN');

-- Manager: Station-scoped read access
CREATE POLICY manager_assigned_stations_only ON stations
    FOR SELECT
    TO authenticated
    USING (
        auth.jwt() ->> 'role' = 'MANAGER' AND
        id IN (SELECT station_id FROM user_stations WHERE user_id = auth.uid())
    );

-- Realtime publication for IoT events
DO $$ BEGIN
    CREATE PUBLICATION supabase_realtime FOR TABLE fuel_transactions, tanks, system_alerts, fcc_devices;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
