-- Enable extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- RELATIONAL TABLES (PostgreSQL)
-- ============================================================

CREATE TABLE organisations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    plan            TEXT NOT NULL DEFAULT 'starter'
                    CHECK (plan IN ('starter', 'pro', 'enterprise')),
    max_chargers    INT NOT NULL DEFAULT 100,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member'
                    CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE chargers (
    cp_id           TEXT PRIMARY KEY,
    org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    display_name    TEXT,
    vendor          TEXT,
    model           TEXT,
    firmware_version TEXT,
    serial_number   TEXT,
    connector_count INT NOT NULL DEFAULT 1,
    location        GEOGRAPHY(POINT, 4326),
    address         TEXT,
    city            TEXT,
    state           TEXT,
    pincode         TEXT,
    status          TEXT NOT NULL DEFAULT 'offline'
                    CHECK (status IN ('online', 'offline', 'faulted', 'unknown')),
    health_score    FLOAT NOT NULL DEFAULT 100.0
                    CHECK (health_score >= 0 AND health_score <= 100),
    last_boot_at    TIMESTAMPTZ,
    last_heartbeat_at TIMESTAMPTZ,
    last_session_at TIMESTAMPTZ,
    commissioned_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chargers_org ON chargers(org_id);
CREATE INDEX idx_chargers_status ON chargers(status);
CREATE INDEX idx_chargers_health ON chargers(health_score);

CREATE TABLE incidents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cp_id           TEXT NOT NULL REFERENCES chargers(cp_id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    severity        TEXT NOT NULL
                    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    failure_type    TEXT
                    CHECK (failure_type IN (
                        'power_supply', 'connector_fault', 'communication_loss',
                        'payment_system', 'firmware_crash', 'thermal_overload',
                        'ground_fault', 'unknown'
                    )),
    anomaly_score   FLOAT,
    title           TEXT NOT NULL,
    description     TEXT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolution_notes TEXT,
    confirmed_failure_type TEXT,
    auto_detected   BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_incidents_org ON incidents(org_id, detected_at DESC);
CREATE INDEX idx_incidents_cp ON incidents(cp_id, detected_at DESC);
CREATE INDEX idx_incidents_open ON incidents(org_id) WHERE resolved_at IS NULL;

CREATE TABLE alert_configs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL
                    CHECK (channel IN ('sms', 'whatsapp', 'email', 'webhook', 'slack')),
    endpoint        TEXT NOT NULL,
    label           TEXT,
    severity_min    TEXT NOT NULL DEFAULT 'medium'
                    CHECK (severity_min IN ('low', 'medium', 'high', 'critical')),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alerts_org ON alert_configs(org_id);

CREATE TABLE ml_models (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cp_id           TEXT REFERENCES chargers(cp_id) ON DELETE CASCADE,
    model_type      TEXT NOT NULL
                    CHECK (model_type IN (
                        'anomaly_detector', 'failure_classifier', 'ttf_predictor'
                    )),
    version         INT NOT NULL DEFAULT 1,
    trained_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    training_samples INT,
    metrics         JSONB,
    model_path      TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TIME-SERIES TABLES (TimescaleDB Hypertables)
-- ============================================================

CREATE TABLE ocpp_events (
    time            TIMESTAMPTZ NOT NULL,
    cp_id           TEXT NOT NULL,
    org_id          UUID NOT NULL,
    event_type      TEXT NOT NULL,
    connector_id    INT,
    payload         JSONB NOT NULL,
    raw_frame       JSONB
);
SELECT create_hypertable('ocpp_events', 'time');
CREATE INDEX idx_ocpp_events_cp ON ocpp_events (cp_id, time DESC);
CREATE INDEX idx_ocpp_events_type ON ocpp_events (event_type, time DESC);

SELECT add_retention_policy('ocpp_events', INTERVAL '90 days');

CREATE TABLE feature_vectors (
    time            TIMESTAMPTZ NOT NULL,
    cp_id           TEXT NOT NULL,
    org_id          UUID NOT NULL,
    features        FLOAT8[24] NOT NULL,
    anomaly_score   FLOAT8,
    is_anomaly      BOOLEAN,
    failure_type    TEXT,
    failure_confidence FLOAT8
);
SELECT create_hypertable('feature_vectors', 'time');
CREATE INDEX idx_features_cp ON feature_vectors (cp_id, time DESC);
CREATE INDEX idx_features_anomaly ON feature_vectors (cp_id, time DESC)
    WHERE is_anomaly = true;

SELECT add_retention_policy('feature_vectors', INTERVAL '365 days');

CREATE TABLE charger_sessions (
    id              BIGSERIAL,
    time            TIMESTAMPTZ NOT NULL,
    cp_id           TEXT NOT NULL,
    org_id          UUID NOT NULL,
    connector_id    INT NOT NULL,
    transaction_id  INT,
    id_tag          TEXT,
    meter_start     INT,
    meter_stop      INT,
    energy_kwh      FLOAT,
    duration_min    FLOAT,
    stop_reason     TEXT,
    started_at      TIMESTAMPTZ NOT NULL,
    stopped_at      TIMESTAMPTZ
);
SELECT create_hypertable('charger_sessions', 'time');
CREATE INDEX idx_sessions_cp ON charger_sessions (cp_id, time DESC);

-- ============================================================
-- CONTINUOUS AGGREGATES
-- ============================================================

CREATE MATERIALIZED VIEW charger_uptime_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    cp_id,
    org_id,
    COUNT(*) FILTER (WHERE event_type = 'heartbeat') AS heartbeat_count,
    COUNT(*) FILTER (WHERE event_type = 'status'
        AND payload->>'status' = 'Faulted') AS faulted_count,
    COUNT(*) FILTER (WHERE event_type = 'status'
        AND payload->>'status' = 'Available') AS available_count
FROM ocpp_events
GROUP BY bucket, cp_id, org_id;

SELECT add_continuous_aggregate_policy('charger_uptime_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

CREATE MATERIALIZED VIEW charger_sessions_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    cp_id,
    org_id,
    COUNT(*) AS total_sessions,
    COUNT(*) FILTER (WHERE stop_reason = 'EVDisconnected') AS successful_sessions,
    COUNT(*) FILTER (WHERE stop_reason != 'EVDisconnected'
        AND stop_reason IS NOT NULL) AS failed_sessions,
    AVG(energy_kwh) AS avg_energy_kwh,
    AVG(duration_min) AS avg_duration_min
FROM charger_sessions
GROUP BY bucket, cp_id, org_id;

SELECT add_continuous_aggregate_policy('charger_sessions_daily',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
