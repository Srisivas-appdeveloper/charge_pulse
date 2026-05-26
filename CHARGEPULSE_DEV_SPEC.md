# ChargePulse — Complete Development Specification
## EV Charging Station Reliability & Fault Prediction SaaS

> **Purpose of this document:** This is the single source of truth for building ChargePulse using Claude Code. Every file, every function, every database table, every API endpoint is specified here. Follow this document exactly when prompting Claude Code.

---

## TABLE OF CONTENTS

1. Project Overview
2. Tech Stack & Dependencies
3. Project Structure
4. Environment Setup
5. Database Schema (Complete SQL)
6. OCPP Gateway (Full Spec)
7. Feature Engineering Pipeline
8. ML Models (Complete Architecture)
9. API Endpoints (Full Spec)
10. Alert System
11. React Dashboard
12. Authentication & Multi-Tenancy
13. Deployment
14. Sprint Plan (Week-by-Week Tasks)
15. Testing Strategy
16. Future Roadmap

---

## 1. PROJECT OVERVIEW

### What is ChargePulse?
A pure-software SaaS that predicts EV charger failures before they happen by analysing OCPP protocol telemetry with custom-built ML models. Zero dependency on any third-party AI/LLM platform.

### How it works (simple flow):
```
EV Charger (hardware, already exists)
    │
    │ OCPP 1.6 / 2.0.1 over WebSocket
    │
    ▼
ChargePulse OCPP Gateway (our Python server)
    │
    │ Stores every message
    │
    ▼
Feature Engine (extracts 24 metrics per charger per 15 min)
    │
    ▼
ML Models (custom PyTorch + XGBoost, trained from scratch)
    │
    │ Detects anomalies, classifies failures, predicts time-to-failure
    │
    ▼
Alert Engine → SMS / WhatsApp / Email / Webhook
    │
    ▼
React Dashboard (fleet map, health scores, incidents)
```

### Business model:
- ₹200/charger/month (Starter: alerts only)
- ₹400/charger/month (Pro: predictions + analytics)
- ₹500/charger/month (Enterprise: custom models + API)

### Target customers (India-first):
- Tier-2/Tier-3 CPOs: ChargeZone, Statiq, Zeon, Bolt.Earth, GLIDA, Charzer
- Fleet charging operators: Blu-Smart, Lithium Urban
- Real estate operators managing 5-50 chargers

---

## 2. TECH STACK & DEPENDENCIES

### Backend (Python 3.12)
```
# Core
fastapi==0.115.*
uvicorn[standard]==0.32.*
websockets==13.*
ocpp==2.1.*               # mobilityhouse/ocpp — OCPP 1.6 + 2.0.1
pydantic==2.*
python-jose[cryptography]  # JWT auth
passlib[bcrypt]            # Password hashing
python-multipart           # Form data

# Database
asyncpg==0.30.*           # Async PostgreSQL driver
sqlalchemy==2.*           # ORM (async mode)
alembic==1.*              # DB migrations
redis[hiredis]==5.*       # Redis client with C speedup

# ML (all from-scratch, no pre-trained models)
torch==2.4.*              # LSTM Autoencoder — custom architecture
xgboost==2.1.*            # Failure classifier
scikit-learn==1.5.*       # Preprocessing, metrics, utilities
scikit-survival==0.23.*   # Time-to-failure survival models
numpy==1.26.*
pandas==2.*

# Alerts
httpx==0.27.*             # Async HTTP client (for webhook/WhatsApp API calls)

# Utilities
python-dotenv
structlog                 # Structured logging
apscheduler==3.10.*       # Scheduled jobs (model retraining, feature extraction)
```

### Frontend (React 18)
```
react@18
react-dom@18
react-router-dom@6
@tanstack/react-query@5    # Data fetching + caching
recharts@2                 # Charts
leaflet + react-leaflet    # Fleet map
tailwindcss@3              # Styling
lucide-react               # Icons
axios                      # API client
date-fns                   # Date utilities
```

### Infrastructure
```
PostgreSQL 16 + TimescaleDB 2.x   # Time-series + relational
Redis 7                            # Streams + cache
Docker + Docker Compose            # Local dev + deployment
Nginx                              # Reverse proxy + SSL termination
```

---

## 3. PROJECT STRUCTURE

```
chargepulse/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .env
├── README.md
├── CHARGEPULSE_DEV_SPEC.md          # THIS FILE
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/                 # DB migration files
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app factory
│   │   ├── config.py                 # Settings from .env
│   │   ├── dependencies.py           # FastAPI dependency injection
│   │   │
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/v1/auth/*
│   │   │   ├── service.py            # Login, register, JWT logic
│   │   │   ├── models.py             # User, Organisation SQLAlchemy models
│   │   │   └── schemas.py            # Pydantic request/response schemas
│   │   │
│   │   ├── chargers/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/v1/chargers/*
│   │   │   ├── service.py            # CRUD + health score computation
│   │   │   ├── models.py             # Charger SQLAlchemy model
│   │   │   └── schemas.py
│   │   │
│   │   ├── incidents/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/v1/incidents/*
│   │   │   ├── service.py            # Incident CRUD + resolution tracking
│   │   │   ├── models.py             # Incident SQLAlchemy model
│   │   │   └── schemas.py
│   │   │
│   │   ├── analytics/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/v1/analytics/*
│   │   │   └── service.py            # Uptime, MTBF, vendor comparison
│   │   │
│   │   ├── alerts/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/v1/alerts/*
│   │   │   ├── service.py            # Alert config CRUD
│   │   │   ├── dispatcher.py         # Send SMS/WhatsApp/email/webhook
│   │   │   ├── models.py             # AlertConfig SQLAlchemy model
│   │   │   └── schemas.py
│   │   │
│   │   ├── fleet/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/v1/fleet/*
│   │   │   └── service.py            # Fleet overview, map data
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── session.py            # Async SQLAlchemy session
│   │       ├── base.py               # Declarative base
│   │       └── timescale.py          # TimescaleDB raw query helpers
│   │
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── server.py                 # OCPP WebSocket server (main entry)
│   │   ├── handler_v16.py            # OCPP 1.6 message handlers
│   │   ├── handler_v201.py           # OCPP 2.0.1 message handlers
│   │   ├── message_router.py         # Publish to Redis Streams
│   │   ├── heartbeat_watchdog.py     # Detect silent disconnects
│   │   └── vendor_profiles/
│   │       ├── __init__.py
│   │       ├── base.py               # Base vendor profile class
│   │       ├── delta.py
│   │       ├── abb.py
│   │       ├── exicom.py
│   │       ├── servotech.py
│   │       └── generic.py            # Fallback for unknown vendors
│   │
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── features.py               # Feature extraction (24-dim vector)
│   │   ├── feature_consumer.py       # Redis Stream consumer → feature vectors
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── anomaly_detector.py   # LSTM Autoencoder (PyTorch)
│   │   │   ├── failure_classifier.py # XGBoost failure type classifier
│   │   │   └── ttf_predictor.py      # Time-to-failure survival model
│   │   ├── training/
│   │   │   ├── __init__.py
│   │   │   ├── train_anomaly.py      # Training script for LSTM autoencoder
│   │   │   ├── train_classifier.py   # Training script for XGBoost
│   │   │   ├── train_ttf.py          # Training script for survival model
│   │   │   └── data_loader.py        # Load feature vectors from TimescaleDB
│   │   ├── inference.py              # Real-time scoring pipeline
│   │   ├── rules.py                  # Rule-based alert engine (Phase 1)
│   │   └── model_store/              # Saved .pt and .xgb model files
│   │       └── .gitkeep
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── feature_worker.py         # Consumes Redis → computes features → stores
│   │   ├── inference_worker.py        # Runs ML inference on feature vectors
│   │   ├── alert_worker.py           # Checks anomaly scores → dispatches alerts
│   │   ├── health_score_worker.py    # Recomputes charger health scores hourly
│   │   └── training_scheduler.py     # Nightly model retraining cron
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py               # Pytest fixtures (DB, Redis, test client)
│       ├── test_gateway/
│       │   ├── test_ocpp_v16.py
│       │   └── test_heartbeat.py
│       ├── test_api/
│       │   ├── test_auth.py
│       │   ├── test_chargers.py
│       │   └── test_incidents.py
│       ├── test_ml/
│       │   ├── test_features.py
│       │   ├── test_anomaly_detector.py
│       │   └── test_rules.py
│       └── test_workers/
│           └── test_feature_worker.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.js
│   ├── index.html
│   ├── public/
│   │   └── favicon.ico
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/
│       │   ├── client.js              # Axios instance with auth interceptor
│       │   ├── auth.js                # Login, register API calls
│       │   ├── chargers.js            # Charger CRUD API calls
│       │   ├── incidents.js           # Incident API calls
│       │   ├── fleet.js               # Fleet overview API calls
│       │   ├── analytics.js           # Analytics API calls
│       │   └── alerts.js              # Alert config API calls
│       ├── hooks/
│       │   ├── useAuth.js             # Auth context + JWT management
│       │   ├── useChargers.js         # React Query hooks for chargers
│       │   └── useWebSocket.js        # Real-time charger status feed
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Register.jsx
│       │   ├── Dashboard.jsx          # Main fleet overview
│       │   ├── FleetMap.jsx           # Leaflet map with charger pins
│       │   ├── ChargerDetail.jsx      # Single charger health + telemetry
│       │   ├── Incidents.jsx          # Incident list + filters
│       │   ├── IncidentDetail.jsx     # Single incident + resolution form
│       │   ├── Analytics.jsx          # Uptime charts, vendor comparison
│       │   ├── Predictions.jsx        # Upcoming predicted failures
│       │   ├── AlertConfig.jsx        # Manage alert channels
│       │   └── Settings.jsx           # Org settings, billing
│       ├── components/
│       │   ├── Layout.jsx             # Sidebar + topbar wrapper
│       │   ├── Sidebar.jsx
│       │   ├── HealthBadge.jsx        # Color-coded health score pill
│       │   ├── ChargerStatusDot.jsx   # Green/amber/red status indicator
│       │   ├── AnomalyTimeline.jsx    # Timeline chart of anomaly scores
│       │   ├── UptimeChart.jsx        # Line chart of uptime %
│       │   ├── FeatureRadar.jsx       # Radar chart showing which features are anomalous
│       │   └── IncidentCard.jsx       # Compact incident summary card
│       └── utils/
│           ├── constants.js
│           └── formatters.js          # Date, currency, percentage formatters
│
├── scripts/
│   ├── seed_demo_data.py              # Generate demo chargers + events for testing
│   ├── simulate_charger.py            # Run OCPP simulator against gateway
│   ├── export_training_data.py        # Export feature vectors for model training
│   └── deploy.sh                      # Production deployment script
│
└── nginx/
    ├── nginx.conf                     # Production nginx config
    └── ssl/                           # SSL certificates (Let's Encrypt)
```

---

## 4. ENVIRONMENT SETUP

### .env.example
```bash
# === Database ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chargepulse
POSTGRES_USER=chargepulse
POSTGRES_PASSWORD=change_me_in_production

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === JWT Auth ===
JWT_SECRET_KEY=generate-a-64-char-random-string-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# === OCPP Gateway ===
OCPP_GATEWAY_HOST=0.0.0.0
OCPP_GATEWAY_PORT=9000
OCPP_HEARTBEAT_INTERVAL=60
OCPP_HEARTBEAT_TIMEOUT=300

# === Alerts ===
MSG91_AUTH_KEY=your_msg91_key
MSG91_SENDER_ID=CHGPLS
MSG91_TEMPLATE_ID=your_template_id

SMTP_HOST=email-smtp.ap-south-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your_ses_smtp_user
SMTP_PASSWORD=your_ses_smtp_password
SMTP_FROM=alerts@chargepulse.in

WHATSAPP_API_URL=https://graph.facebook.com/v18.0
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_ACCESS_TOKEN=your_token

# === ML ===
MODEL_STORE_PATH=./ml/model_store
FEATURE_WINDOW_MINUTES=15
ANOMALY_THRESHOLD=0.5
TRAINING_SCHEDULE_CRON=0 2 * * *

# === App ===
APP_ENV=development
APP_DEBUG=true
CORS_ORIGINS=http://localhost:5173
```

### docker-compose.yml
```yaml
version: "3.9"

services:
  postgres:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: chargepulse
      POSTGRES_USER: chargepulse
      POSTGRES_PASSWORD: change_me_in_production
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/init.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  backend:
    build: ./backend
    command: >
      bash -c "
        alembic upgrade head &&
        uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
      "
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  gateway:
    build: ./backend
    command: python -m gateway.server
    ports:
      - "9000:9000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  feature_worker:
    build: ./backend
    command: python -m workers.feature_worker
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  inference_worker:
    build: ./backend
    command: python -m workers.inference_worker
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  alert_worker:
    build: ./backend
    command: python -m workers.alert_worker
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  pgdata:
```

### Backend Dockerfile
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 8000 9000
```

---

## 5. DATABASE SCHEMA (Complete SQL)

### init.sql — Run on first setup
```sql
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
    confirmed_failure_type TEXT,       -- Human-labeled ground truth for ML training
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
    endpoint        TEXT NOT NULL,       -- Phone number / email / URL
    label           TEXT,                -- "CTO Phone", "Ops Team Slack"
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
    metrics         JSONB,               -- {"mse": 0.02, "threshold": 0.5, "f1": 0.85}
    model_path      TEXT NOT NULL,        -- Relative path in model_store/
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

-- Retention: auto-drop raw events older than 90 days
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

-- Retention: keep feature vectors for 1 year
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
-- CONTINUOUS AGGREGATES (for fast dashboard queries)
-- ============================================================

-- Hourly uptime per charger
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

-- Daily session stats per charger
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
```

---

## 6. OCPP GATEWAY (Full Spec)

### 6.1 Connection Flow
1. Charger connects: `wss://csms.chargepulse.io/ocpp/{charge_point_id}`
2. Gateway checks subprotocol header (`ocpp1.6` or `ocpp2.0.1`)
3. Looks up `charge_point_id` in `chargers` table → gets `org_id`
4. If not found → reject connection (or auto-register if org allows)
5. Creates handler instance (v16 or v201 based on subprotocol)
6. All messages are published to Redis Stream `stream:ocpp:{cp_id}`

### 6.2 OCPP 1.6 Messages to Handle

**Charger → Server (must handle all):**

| Message | Handler Logic |
|---------|---------------|
| `BootNotification` | Store vendor/model/firmware. Update charger record. Return `Accepted` + heartbeat interval. |
| `Heartbeat` | Update `last_heartbeat_at`. Publish to stream. Return current time. |
| `StatusNotification` | Store connector status + error code. Detect Faulted transitions. Publish. |
| `MeterValues` | Parse sampled values (energy, power, voltage, current, SoC, temperature). Publish. |
| `StartTransaction` | Create session record. Generate transaction_id. Return `Accepted`. |
| `StopTransaction` | Complete session record. Calculate energy/duration. Log stop reason. |
| `Authorize` | Return `Accepted` (we don't manage auth cards — the CPO's system does). |
| `DataTransfer` | Log vendor-specific data. Return `Accepted`. |
| `DiagnosticsStatusNotification` | Log diagnostic upload status. |
| `FirmwareStatusNotification` | Log firmware update progress. |

**Server → Charger (command capability):**

| Command | When to Use |
|---------|------------|
| `TriggerMessage` | Force a StatusNotification on demand |
| `Reset` | Remote reboot when firmware crash detected |
| `ChangeConfiguration` | Tune heartbeat interval, meter sampling rate |
| `GetDiagnostics` | Pull charger diagnostic logs |
| `RemoteStartTransaction` | Health check: test if charger responds |
| `RemoteStopTransaction` | Emergency stop |

### 6.3 Vendor Profile System

Each charger vendor has quirks. The vendor profile normalizes them:

```python
# gateway/vendor_profiles/base.py
class VendorProfile:
    """Base class. Override methods for vendor-specific behavior."""

    vendor_name: str = "generic"

    def normalize_status(self, raw_status: str) -> str:
        """Map vendor-specific status strings to standard ones."""
        return raw_status

    def normalize_error_code(self, raw_code: str) -> str:
        """Map vendor-specific error codes to standard categories."""
        return raw_code

    def normalize_meter_values(self, raw_values: list) -> dict:
        """Normalize measurand names and units."""
        return raw_values

    def get_heartbeat_interval(self) -> int:
        """Recommended heartbeat interval for this vendor."""
        return 60

    def get_meter_sample_interval(self) -> int:
        """Recommended MeterValues sampling interval (seconds)."""
        return 30
```

### 6.4 Heartbeat Watchdog

Runs as a background task in the gateway process:

```
Every 30 seconds:
  For each connected charger:
    If (now - last_heartbeat) > HEARTBEAT_TIMEOUT (default 300s):
      → Mark charger as "offline"
      → Publish "disconnect" event to Redis Stream
      → Create incident if first disconnect in 1 hour
```

---

## 7. FEATURE ENGINEERING PIPELINE

### 7.1 The 24-Feature Vector

Computed every 15 minutes per charger from raw OCPP events:

```
FEATURE INDEX | NAME                    | SOURCE                    | TYPE
------------- | ----------------------- | ------------------------- | -----
0             | sessions_started        | StartTransaction count    | int
1             | sessions_completed      | StopTransaction (normal)  | int
2             | sessions_failed         | StopTransaction (abnormal)| int
3             | avg_session_duration_min | Session records           | float
4             | avg_energy_delivered_kwh | MeterValues               | float
5             | session_completion_rate  | completed / total         | float
6             | avg_power_kw            | MeterValues (Power.Active) | float
7             | std_power_kw            | MeterValues std dev       | float
8             | max_voltage_v           | MeterValues (Voltage)     | float
9             | min_voltage_v           | MeterValues (Voltage)     | float
10            | avg_current_a           | MeterValues (Current)     | float
11            | power_factor            | Real / Apparent power     | float
12            | status_transitions      | StatusNotification count  | int
13            | time_in_faulted_pct     | StatusNotification        | float
14            | time_in_available_pct   | StatusNotification        | float
15            | time_in_unavailable_pct | StatusNotification        | float
16            | error_code_count        | Non-NoError status msgs   | int
17            | unique_error_codes      | Distinct error types      | int
18            | heartbeat_count         | Heartbeat count           | int
19            | heartbeat_gap_max_sec   | Max gap between heartbeats| float
20            | heartbeat_gap_std_sec   | Std dev of HB intervals   | float
21            | ws_reconnections        | WebSocket reconnect events| int
22            | hour_of_day_sin         | sin(2π × hour/24)         | float
23            | day_of_week_sin         | sin(2π × day/7)           | float
```

### 7.2 Feature Worker Process

```
Redis Stream consumer (consumer group: "feature_engine")
  │
  │ Reads events from stream:ocpp:{cp_id}
  │ Buffers events in memory per 15-min window
  │
  Every 15 minutes per charger:
  │ 1. Query all events in [window_start, window_end]
  │ 2. Compute 24-feature vector
  │ 3. Normalize features (z-score using running mean/std)
  │ 4. Store in feature_vectors hypertable
  │ 5. Publish feature vector to stream:features:{cp_id}
  │    (for inference worker to consume)
```

---

## 8. ML MODELS (Complete Architecture)

### 8.1 Model A: LSTM Autoencoder (Anomaly Detection)

**Purpose:** Learn what "normal" looks like for each charger. High reconstruction error = anomaly.

```
Architecture:
  Input:  (batch, 96, 24)  — last 96 windows (24 hours) × 24 features
  Encoder LSTM: 24 → 64 hidden, 2 layers, dropout 0.2
  Encoder FC:   64 → 32 (latent space)
  Decoder FC:   32 → 64
  Decoder LSTM: 64 → 64 hidden, 2 layers, dropout 0.2
  Output FC:    64 → 24

  Loss: MSE between input and reconstructed output
  Optimizer: Adam, lr=0.001, weight_decay=1e-5

Training:
  - One model per charger station
  - Train on first 14 days of "normal" data (no known incidents)
  - Validation split: 80/20
  - Epochs: 50 with early stopping (patience=10)
  - Threshold: set at 95th percentile of training reconstruction error

Inference:
  - Every 15 min: feed last 24 hours of feature vectors
  - Compute reconstruction error on latest window
  - If error > threshold → anomaly detected
  - Return: anomaly_score, is_anomaly, top_anomalous_features
```

### 8.2 Model B: XGBoost Failure Classifier

**Purpose:** When anomaly detected, classify what type of failure is likely.

```
Architecture:
  Input:  28 features (24 base + anomaly_score + top_3_feature_errors)
  Output: 7 classes (power_supply, connector_fault, communication_loss,
          payment_system, firmware_crash, thermal_overload, ground_fault)

  XGBoost params:
    n_estimators: 200
    max_depth: 6
    learning_rate: 0.1
    objective: multi:softprob
    eval_metric: mlogloss
    subsample: 0.8
    colsample_bytree: 0.8

Training:
  - Requires labeled incidents (confirmed_failure_type in incidents table)
  - Minimum 500 labeled incidents before model is useful
  - Until then: use rule-based classification
  - Retrain weekly as new labeled data accumulates
  - Cross-validation: 5-fold stratified
```

### 8.3 Model C: Time-to-Failure Predictor

**Purpose:** "Charger X will likely fail within Y hours."

```
Architecture:
  Survival model: Cox Proportional Hazards (scikit-survival)
  Input:  24 base features + health_score + days_since_last_incident
  Output: Survival function → estimated time to next failure

  Alternative: Random Survival Forest if Cox PH assumptions violated

Training:
  - Event: charger enters Faulted state or is reported broken
  - Censoring: charger is still running (right-censored)
  - Requires 3+ months of data with 100+ failure events
  - Until then: use simple degradation heuristic
    (health_score decay rate extrapolation)
```

### 8.4 Rule-Based Engine (Phase 1 — ships before ML is ready)

```python
RULES = {
    "heartbeat_missing": {
        "condition": "heartbeat_gap_max_sec > 300",
        "severity": "high",
        "failure_type": "communication_loss",
        "title": "Charger stopped responding",
    },
    "faulted_state": {
        "condition": "time_in_faulted_pct > 0.10",
        "severity": "critical",
        "failure_type": "connector_fault",
        "title": "Charger in faulted state",
    },
    "voltage_low": {
        "condition": "min_voltage_v > 0 AND min_voltage_v < 200",
        "severity": "high",
        "failure_type": "power_supply",
        "title": "Low voltage detected",
    },
    "voltage_high": {
        "condition": "max_voltage_v > 260",
        "severity": "high",
        "failure_type": "power_supply",
        "title": "High voltage spike detected",
    },
    "session_failures_spike": {
        "condition": "session_completion_rate < 0.70 AND sessions_started >= 3",
        "severity": "medium",
        "failure_type": "connector_fault",
        "title": "High session failure rate",
    },
    "power_instability": {
        "condition": "std_power_kw > 5.0 AND avg_power_kw > 1.0",
        "severity": "medium",
        "failure_type": "power_supply",
        "title": "Unstable power delivery",
    },
    "frequent_reboots": {
        "condition": "ws_reconnections >= 3",
        "severity": "high",
        "failure_type": "firmware_crash",
        "title": "Charger rebooting repeatedly",
    },
    "zero_sessions_during_peak": {
        "condition": "sessions_started == 0 AND hour_of_day_sin > 0.5",
        "severity": "low",
        "failure_type": "unknown",
        "title": "No sessions during peak hours",
    },
}
```

### 8.5 Health Score Computation

```
health_score (0-100) = weighted combination of:
  - Recent anomaly frequency (weight: 0.3)
      = 100 - (anomalies in last 7 days / total windows in 7 days) × 100
  - Session completion rate (weight: 0.2)
      = avg completion rate over last 7 days × 100
  - Uptime percentage (weight: 0.3)
      = (time_in_available + time_in_charging) / total_time × 100
  - Connectivity stability (weight: 0.2)
      = 100 - (avg heartbeat_gap_std / heartbeat_interval) × 100

Recomputed hourly by health_score_worker.
Stored in chargers.health_score.
```

---

## 9. API ENDPOINTS (Full Spec)

### Base URL: `/api/v1`
### Auth: Bearer JWT token in Authorization header (except login/register)

### 9.1 Authentication
```
POST /auth/register
  Body: { org_name, email, password, full_name }
  Response: { access_token, user, organisation }

POST /auth/login
  Body: { email, password }
  Response: { access_token, user, organisation }

GET /auth/me
  Response: { user, organisation }
```

### 9.2 Chargers
```
GET /chargers
  Query: ?status=online&health_below=50&page=1&limit=20
  Response: { chargers: [...], total, page, pages }

POST /chargers
  Body: { cp_id, display_name, address, city, state, pincode, lat, lng }
  Response: { charger }

GET /chargers/{cp_id}
  Response: { charger, recent_incidents, current_anomaly_score }

GET /chargers/{cp_id}/health
  Query: ?from=2026-01-01&to=2026-01-31
  Response: { timeline: [{ time, health_score, anomaly_score }] }

GET /chargers/{cp_id}/telemetry
  Query: ?from=...&to=...&event_type=meter
  Response: { events: [...] }

GET /chargers/{cp_id}/sessions
  Query: ?from=...&to=...&page=1&limit=20
  Response: { sessions: [...], total }

POST /chargers/{cp_id}/command
  Body: { command: "Reset", params: { type: "Soft" } }
  Response: { status: "sent", response: {...} }
```

### 9.3 Fleet
```
GET /fleet/overview
  Response: {
    total_chargers, online, offline, faulted,
    avg_health_score, avg_uptime_7d,
    open_incidents, critical_incidents,
    sessions_today, energy_today_kwh
  }

GET /fleet/map
  Response: {
    chargers: [{ cp_id, display_name, lat, lng, status, health_score }]
  }

GET /fleet/uptime
  Query: ?from=...&to=...&granularity=daily
  Response: { timeline: [{ date, uptime_pct, chargers_online }] }
```

### 9.4 Incidents
```
GET /incidents
  Query: ?severity=critical&failure_type=power_supply&resolved=false&page=1
  Response: { incidents: [...], total }

GET /incidents/{id}
  Response: { incident, charger, anomaly_details, timeline }

PATCH /incidents/{id}
  Body: { acknowledged_at?, resolved_at?, resolution_notes?,
          confirmed_failure_type? }
  Response: { incident }
```

### 9.5 Analytics
```
GET /analytics/reliability
  Query: ?from=...&to=...&group_by=vendor
  Response: { groups: [{ name, mtbf_hours, mttr_hours, uptime_pct }] }

GET /analytics/predictions
  Response: { predictions: [{
    cp_id, display_name, predicted_failure_type,
    confidence, estimated_hours_to_failure
  }] }

GET /analytics/vendor-comparison
  Response: { vendors: [{
    vendor, model, charger_count, avg_health,
    avg_uptime, incident_rate
  }] }
```

### 9.6 Alerts
```
GET /alerts/config
  Response: { configs: [...] }

POST /alerts/config
  Body: { channel, endpoint, label, severity_min }
  Response: { config }

PUT /alerts/config/{id}
  Body: { endpoint?, label?, severity_min?, is_active? }
  Response: { config }

DELETE /alerts/config/{id}
  Response: { ok: true }
```

### 9.7 WebSocket (Real-time)
```
WS /ws/live
  Auth: ?token=<jwt>
  Server pushes:
    { type: "status_change", cp_id, status, timestamp }
    { type: "anomaly", cp_id, score, failure_type, timestamp }
    { type: "incident", incident_id, cp_id, severity, title, timestamp }
    { type: "health_update", cp_id, health_score, timestamp }
```

---

## 10. ALERT SYSTEM

### Alert Flow
```
Anomaly detected (rule or ML)
  │
  ▼
Create incident record in DB
  │
  ▼
Query alert_configs for this org where severity >= incident severity
  │
  ▼
For each matching config:
  │
  ├─ SMS (MSG91):    POST https://api.msg91.com/api/v5/flow/
  ├─ WhatsApp:       POST https://graph.facebook.com/v18.0/{phone_id}/messages
  ├─ Email (SES):    SMTP send via aiosmtplib
  ├─ Webhook:        POST {endpoint} with JSON payload
  └─ Slack:          POST {webhook_url} with Slack block format
```

### Alert Message Template
```
🔴 ChargePulse Alert

Charger: {display_name} ({cp_id})
Location: {address}
Severity: {severity}
Issue: {title}
Score: {anomaly_score}/1.0
Detected: {detected_at}

View: https://app.chargepulse.in/incidents/{incident_id}
```

### Deduplication
- Don't send duplicate alerts for same charger + same failure_type within 1 hour
- Rate limit: max 10 alerts per org per hour (configurable)
- Escalation: if incident unresolved for 4 hours → re-alert at next severity level

---

## 11. REACT DASHBOARD

### Pages and Components

**Dashboard (home)**
- Fleet summary cards: total chargers, online %, avg health, open incidents
- Health distribution chart (how many chargers at each health level)
- Recent incidents list (last 10)
- Quick actions: view map, see predictions

**Fleet Map**
- Leaflet map with charger pins
- Pin color: green (health > 80), amber (50-80), red (< 50), gray (offline)
- Click pin → popup with charger name, status, health, link to detail

**Charger Detail**
- Header: name, vendor, model, firmware, status badge, health score gauge
- Tabs: Overview | Telemetry | Sessions | Incidents
- Overview: health timeline chart (Recharts), anomaly score timeline, current feature radar
- Telemetry: raw event log with filters
- Sessions: session list with energy/duration/completion
- Incidents: incident history for this charger

**Incidents**
- Filterable table: severity, failure type, charger, date range, resolved/open
- Bulk actions: acknowledge, assign
- Click → incident detail with anomaly breakdown, resolution form

**Analytics**
- Uptime trend (line chart over time)
- MTBF / MTTR by vendor (bar chart)
- Vendor reliability comparison (table)
- Top 10 most unreliable chargers

**Predictions**
- Table of chargers predicted to fail within 24/48/72 hours
- Sorted by urgency
- Link to charger detail for each

**Alert Config**
- List of alert channels with toggle on/off
- Add new: select channel type, enter endpoint, set severity threshold
- Test button: sends a test alert

### Dashboard Color Scheme
```
Health colors:
  90-100: #10B981 (emerald green)
  70-89:  #F59E0B (amber)
  50-69:  #F97316 (orange)
  0-49:   #EF4444 (red)

Status colors:
  online:    #10B981
  offline:   #6B7280
  faulted:   #EF4444
  charging:  #3B82F6
  available: #10B981

Severity colors:
  critical: #EF4444
  high:     #F97316
  medium:   #F59E0B
  low:      #6B7280
```

---

## 12. AUTHENTICATION & MULTI-TENANCY

### JWT Token Flow
```
1. User POSTs email + password to /auth/login
2. Server validates credentials against users table
3. Server creates JWT with payload: { sub: user_id, org_id: org_id, role: role }
4. Token expires in 24 hours
5. Client stores token in localStorage
6. Client sends token in Authorization: Bearer {token} header
7. Server middleware extracts org_id from token
8. ALL database queries filter by org_id (multi-tenancy)
```

### Multi-Tenancy Rule
**EVERY database query MUST include `WHERE org_id = :org_id`.**
This is enforced at the dependency injection level:

```python
# app/dependencies.py
async def get_current_org(token = Depends(oauth2_scheme)):
    payload = decode_jwt(token)
    return payload["org_id"]

# Used in every router:
@router.get("/chargers")
async def list_chargers(org_id: UUID = Depends(get_current_org)):
    return await service.list_chargers(org_id=org_id)
```

---

## 13. DEPLOYMENT

### Production Setup (Single VPS)
```
Hetzner CPX31 (or CPX41 for scale)
  - Ubuntu 24.04 LTS
  - Docker + Docker Compose
  - Nginx reverse proxy
  - Let's Encrypt SSL (certbot)
  - UFW firewall: allow 80, 443, 9000 (OCPP WebSocket)

Domain setup:
  app.chargepulse.in     → frontend (port 5173 → nginx → 443)
  api.chargepulse.in     → backend  (port 8000 → nginx → 443)
  csms.chargepulse.in    → OCPP gateway (port 9000 → nginx → 443 wss)
```

### Nginx Config (key parts)
```nginx
# OCPP WebSocket — critical: must support persistent WS connections
server {
    listen 443 ssl;
    server_name csms.chargepulse.in;

    location /ocpp/ {
        proxy_pass http://localhost:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;   # 24 hours — OCPP connections are persistent
        proxy_send_timeout 86400s;
    }
}
```

### Backup Strategy
```
- PostgreSQL: pg_dump daily at 02:00 → compress → upload to S3/Backblaze B2
- Redis: RDB snapshot every 6 hours (config: save 21600 1)
- ML models: versioned in model_store/, backed up with DB
- Retention: keep 30 daily backups, 12 monthly backups
```

---

## 14. SPRINT PLAN (Week-by-Week Tasks for Claude Code)

### WEEK 1 — Foundation + OCPP Gateway

**Day 1-2: Project scaffolding**
```
Prompt for Claude Code:
"Set up a Python monorepo with FastAPI backend and React frontend.
Use the project structure from CHARGEPULSE_DEV_SPEC.md Section 3.
Create docker-compose.yml with TimescaleDB, Redis, backend, frontend.
Create .env.example with all variables from Section 4.
Initialize alembic for database migrations.
Create the init.sql from Section 5."
```

**Day 3-4: OCPP Gateway**
```
"Build the OCPP WebSocket gateway in backend/gateway/.
Use the mobilityhouse/ocpp Python library.
Handle BootNotification, Heartbeat, StatusNotification.
Publish all events to Redis Streams.
Test with the ocppsim OCPP charge point simulator."
```

**Day 5-7: Complete OCPP + DB storage**
```
"Add MeterValues, StartTransaction, StopTransaction handlers.
Store all events in the ocpp_events TimescaleDB hypertable.
Create the charger_sessions table and populate on StopTransaction.
Implement the heartbeat watchdog background task.
Add vendor profile system with generic fallback."
```

### WEEK 2 — Feature Engine + Rule-Based Alerts

**Day 1-3: Feature extraction**
```
"Build the feature extraction pipeline in backend/ml/features.py.
Implement the 24-feature vector spec from Section 7.1.
Create the feature_worker that consumes from Redis Streams,
computes features every 15 minutes per charger,
and stores them in the feature_vectors hypertable."
```

**Day 4-5: Rule-based alert engine**
```
"Implement the rule-based alert engine from Section 8.4.
Create the inference_worker that reads feature vectors,
evaluates all 8 rules, creates incidents in the DB.
Implement the alert_worker that dispatches alerts via
email (SMTP), SMS (MSG91 API), and webhook."
```

**Day 6-7: Core API**
```
"Build the FastAPI REST API with JWT authentication.
Implement auth endpoints (register, login, me).
Implement charger CRUD endpoints.
Implement incident list and detail endpoints.
All queries must filter by org_id for multi-tenancy."
```

### WEEK 3 — API Completion + Dashboard Shell

**Day 1-2: Remaining API endpoints**
```
"Implement fleet overview, fleet map, and uptime endpoints.
Implement analytics endpoints (reliability, vendor comparison).
Implement alert config CRUD endpoints.
Implement the WebSocket /ws/live endpoint for real-time updates."
```

**Day 3-5: React dashboard**
```
"Build the React frontend with Tailwind CSS.
Create the Layout with sidebar navigation.
Build the Dashboard page with fleet summary cards.
Build the Fleet Map page using Leaflet.
Build the Charger Detail page with health timeline chart.
Use React Query for all data fetching.
Implement JWT auth flow with login page."
```

**Day 6-7: Dashboard completion**
```
"Build the Incidents page with filterable table.
Build the Incident Detail page with resolution form.
Build the Alert Config page.
Connect WebSocket for real-time status updates.
Add the health score badge component (color-coded)."
```

### WEEK 4 — ML Pipeline

**Day 1-3: LSTM Autoencoder**
```
"Implement the LSTM Autoencoder model in PyTorch.
Architecture: 24 input → 64 hidden → 32 latent → reconstruct.
Create the training script that loads feature vectors from TimescaleDB.
Train on synthetic normal data generated by the OCPP simulator.
Implement the AnomalyScorer class for real-time inference.
Set threshold at 95th percentile of training reconstruction error."
```

**Day 4-5: Integrate ML with pipeline**
```
"Update the inference_worker to run both rule-based and ML scoring.
If ML model exists for a charger → use ML score.
If not → fall back to rules only.
Store anomaly_score and is_anomaly in feature_vectors table.
Create incidents for ML-detected anomalies."
```

**Day 6-7: Health score + predictions dashboard**
```
"Implement health_score_worker that recomputes scores hourly.
Formula from Section 8.5.
Build the Analytics page with uptime charts and vendor comparison.
Build the Predictions page showing chargers predicted to fail."
```

### WEEK 5 — Real Charger Integration + Polish

**Day 1-3: Pilot CPO onboarding**
```
"Create an onboarding script that:
1. Registers a new org and admin user
2. Bulk-imports charger records from CSV
3. Configures default alert channels
4. Generates OCPP gateway connection URLs for each charger

Create documentation for CPOs on how to point their
chargers' OCPP WebSocket URL to our gateway."
```

**Day 4-5: Vendor profile tuning**
```
"Based on real charger data from pilot, create/update vendor profiles.
Fix any message parsing issues.
Add error code dictionaries for the pilot's charger vendors.
Tune alert thresholds based on real baseline data."
```

**Day 6-7: UI polish**
```
"Add loading states, error handling, empty states to all pages.
Add mobile responsive design to dashboard.
Add charger search and filter on fleet page.
Add incident export to CSV.
Add settings page with org profile and billing placeholder."
```

### WEEK 6 — Production Deploy + Launch

**Day 1-2: Production deployment**
```
"Create production docker-compose with:
- Nginx reverse proxy with SSL (Let's Encrypt)
- Production environment variables
- Log rotation
- Automated database backups (daily pg_dump)
Deploy to Hetzner CPX31 VPS.
Set up domain: app.chargepulse.in, api.chargepulse.in, csms.chargepulse.in"
```

**Day 3-4: Landing page**
```
"Build a landing page at chargepulse.in with:
- Hero: 'Predict EV charger failures before they happen'
- Problem statement with India stats
- How it works (3 steps)
- Pricing table
- Demo request form
- Footer with contact"
```

**Day 5-7: Testing + XGBoost classifier**
```
"Write integration tests for:
- OCPP gateway (simulate charger → verify events stored)
- Feature extraction (known events → verify feature vector)
- Rule engine (inject anomaly → verify incident created)
- API endpoints (CRUD operations + auth)
- Alert dispatch (mock SMS/email, verify sent)

Train initial XGBoost failure classifier on
rule-labeled incidents from pilot data."
```

---

## 15. TESTING STRATEGY

### Test Types
```
Unit tests:         Feature extraction, health score computation, rule evaluation
Integration tests:  OCPP gateway + DB, API + DB, Worker + Redis + DB
E2E tests:          Simulate charger → anomaly → incident → alert
Load tests:         Simulate 1000 concurrent charger WebSocket connections
```

### Key Test Scenarios
```
1. Charger connects, sends BootNotification → verify charger record created
2. Charger sends 10 Heartbeats → verify heartbeat tracking works
3. Charger sends StatusNotification(Faulted) → verify incident created
4. Charger stops sending heartbeats → verify watchdog creates disconnect incident
5. MeterValues show voltage < 200V → verify rule triggers alert
6. 100 simulated chargers for 24 hours → verify feature vectors computed correctly
7. Known anomaly pattern → verify LSTM autoencoder flags it
8. Alert dispatched → verify SMS/email/webhook received (mocked)
```

### Test Data Generation
```
scripts/seed_demo_data.py:
  - Create 3 demo organisations
  - Create 50 chargers per org (mixed vendors)
  - Generate 7 days of synthetic OCPP events
  - Include 5 known failure patterns per org

scripts/simulate_charger.py:
  - Run N simulated charge points against the gateway
  - Each follows a realistic usage pattern:
    - Boot → Available → Charging cycles → Heartbeats
  - Inject faults: missed heartbeats, voltage drops, Faulted status
```

---

## 16. FUTURE ROADMAP (Post-MVP)

### Phase 2 (Month 2-4)
- OCPP 2.0.1 full support (Device Model, ISO 15118)
- Automated remediation: send Reset on firmware crash detection
- Mobile app (React Native or Flutter)
- WhatsApp bot for incident management

### Phase 3 (Month 4-8)
- XGBoost classifier fully trained on real labeled data
- Time-to-failure survival model operational
- Fleet optimization: recommend charger placement based on utilization
- FAME-III compliance report generator

### Phase 4 (Month 8-12)
- Multi-region deployment (India + Southeast Asia)
- Insurance integration (uptime certificates for premium discounts)
- Battery swap station monitoring (Sun Mobility / Battery Smart)
- Public API for third-party integrations
- White-label option for large CPOs

---

## APPENDIX A: OCPP Error Codes Reference

```
NoError                    → Normal operation
ConnectorLockFailure       → Physical connector issue
EVCommunicationError       → Vehicle not responding
GroundFailure              → Ground fault detected
HighTemperature            → Overheating
InternalError              → Generic firmware error
LocalListConflict          → Auth list issue
OtherError                 → Vendor-specific
OverCurrentFailure         → Current too high
OverVoltage                → Voltage too high
PowerMeterFailure          → Metering hardware issue
PowerSwitchFailure         → Relay/contactor failure
ReaderFailure              → RFID reader broken
ResetFailure               → Reboot command failed
UnderVoltage               → Voltage too low
WeakSignal                 → Network connectivity poor
```

## APPENDIX B: Indian CPO Contact Targets

```
Company         | Est. Chargers | HQ          | OCPP Version
ChargeZone      | 2,000+        | Mumbai      | 1.6J
Statiq          | 7,000+        | Gurugram    | 1.6J / 2.0.1
Bolt.Earth      | 1,00,000+     | Bangalore   | 1.6J
Tata Power      | 5,500+        | Mumbai      | 1.6J / 2.0.1
GLIDA (Fortum)  | 500+          | New Delhi   | 1.6J
Zeon            | 500+          | Bangalore   | 1.6J
Charzer         | 300+          | Noida       | 1.6J
Exicom          | Manufacturer  | Gurugram    | 1.6J / 2.0.1
```

## APPENDIX C: Key Python Commands

```bash
# Start all services
docker compose up -d

# Run database migrations
docker compose exec backend alembic upgrade head

# Create new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Run tests
docker compose exec backend pytest -v

# Simulate a charger
docker compose exec backend python scripts/simulate_charger.py --count 10

# Seed demo data
docker compose exec backend python scripts/seed_demo_data.py

# Train anomaly model for a charger
docker compose exec backend python -m ml.training.train_anomaly --cp_id CP001

# Export training data
docker compose exec backend python scripts/export_training_data.py --output data/

# View OCPP gateway logs
docker compose logs -f gateway

# View feature worker logs
docker compose logs -f feature_worker
```

---

**END OF SPECIFICATION**

*Last updated: May 2026*
*Version: 1.0*
*Author: Saravanan × Claude*
