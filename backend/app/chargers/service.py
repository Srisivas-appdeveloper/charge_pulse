from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.chargers import schemas


_BASE_COLS = (
    "cp_id, display_name, vendor, model, firmware_version, serial_number, "
    "connector_count, status, health_score, address, city, state, pincode, "
    "ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng, "
    "last_boot_at, last_heartbeat_at, last_session_at, created_at"
)


def _row_to_out(row) -> schemas.ChargerOut:
    return schemas.ChargerOut(**dict(row))


async def list_chargers(
    pool: asyncpg.Pool,
    org_id: UUID,
    *,
    status_filter: str | None,
    health_below: float | None,
    page: int,
    limit: int,
) -> schemas.ChargerListResponse:
    where = ["org_id = $1"]
    params: list = [org_id]
    if status_filter:
        params.append(status_filter)
        where.append(f"status = ${len(params)}")
    if health_below is not None:
        params.append(health_below)
        where.append(f"health_score < ${len(params)}")
    where_sql = " AND ".join(where)

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM chargers WHERE {where_sql}", *params,
        )
        offset = (page - 1) * limit
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"SELECT {_BASE_COLS} FROM chargers WHERE {where_sql} "
            f"ORDER BY created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
            *params,
        )

    pages = max(1, (total + limit - 1) // limit)
    return schemas.ChargerListResponse(
        chargers=[_row_to_out(r) for r in rows],
        total=total, page=page, pages=pages,
    )


async def create_charger(
    pool: asyncpg.Pool, org_id: UUID, req: schemas.ChargerCreate,
) -> schemas.ChargerOut:
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT 1 FROM chargers WHERE cp_id = $1", req.cp_id,
        )
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "cp_id already exists")
        cap = await conn.fetchval(
            "SELECT max_chargers FROM organisations WHERE id = $1", org_id,
        )
        used = await conn.fetchval(
            "SELECT count(*) FROM chargers WHERE org_id = $1", org_id,
        )
        if used >= cap:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "charger quota reached")

        loc_sql = "NULL"
        params: list = [
            req.cp_id, org_id, req.display_name, req.vendor, req.model,
            req.connector_count, req.address, req.city, req.state, req.pincode,
        ]
        if req.lat is not None and req.lng is not None:
            params.extend([req.lng, req.lat])
            loc_sql = f"ST_SetSRID(ST_MakePoint(${len(params)-1}, ${len(params)}), 4326)::geography"

        row = await conn.fetchrow(
            f"""
            INSERT INTO chargers (
                cp_id, org_id, display_name, vendor, model, connector_count,
                address, city, state, pincode, location
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, {loc_sql})
            RETURNING {_BASE_COLS}
            """,
            *params,
        )
    return _row_to_out(row)


async def get_charger(
    pool: asyncpg.Pool, org_id: UUID, cp_id: str,
) -> schemas.ChargerDetailResponse:
    async with pool.acquire() as conn:
        charger_row = await conn.fetchrow(
            f"SELECT {_BASE_COLS} FROM chargers WHERE cp_id = $1 AND org_id = $2",
            cp_id, org_id,
        )
        if not charger_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "charger not found")
        incidents = await conn.fetch(
            """
            SELECT id, severity, failure_type, title, detected_at, resolved_at,
                   anomaly_score
            FROM incidents WHERE cp_id = $1 AND org_id = $2
            ORDER BY detected_at DESC LIMIT 10
            """,
            cp_id, org_id,
        )
        anomaly = await conn.fetchval(
            """
            SELECT anomaly_score FROM feature_vectors
            WHERE cp_id = $1 ORDER BY time DESC LIMIT 1
            """,
            cp_id,
        )
    return schemas.ChargerDetailResponse(
        charger=_row_to_out(charger_row),
        recent_incidents=[dict(i) for i in incidents],
        current_anomaly_score=anomaly,
    )


async def get_health(
    pool: asyncpg.Pool, org_id: UUID, cp_id: str,
    frm: datetime | None, to: datetime | None,
) -> schemas.HealthResponse:
    async with pool.acquire() as conn:
        # confirm charger belongs to org
        ok = await conn.fetchval(
            "SELECT 1 FROM chargers WHERE cp_id=$1 AND org_id=$2", cp_id, org_id,
        )
        if not ok:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "charger not found")
        rows = await conn.fetch(
            """
            SELECT time_bucket('1 hour', time) AS bucket,
                   AVG(anomaly_score) AS anomaly_score
            FROM feature_vectors
            WHERE cp_id = $1
              AND ($2::timestamptz IS NULL OR time >= $2)
              AND ($3::timestamptz IS NULL OR time <= $3)
            GROUP BY bucket ORDER BY bucket
            """,
            cp_id, frm, to,
        )
    # Phase 1 has no health timeline storage yet — return current health alongside anomalies.
    return schemas.HealthResponse(
        timeline=[
            schemas.HealthPoint(time=r["bucket"], health_score=None,
                                anomaly_score=r["anomaly_score"])
            for r in rows
        ]
    )


async def get_telemetry(
    pool: asyncpg.Pool, org_id: UUID, cp_id: str,
    frm: datetime | None, to: datetime | None, event_type: str | None,
    limit: int = 500,
) -> schemas.TelemetryResponse:
    async with pool.acquire() as conn:
        ok = await conn.fetchval(
            "SELECT 1 FROM chargers WHERE cp_id=$1 AND org_id=$2", cp_id, org_id,
        )
        if not ok:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "charger not found")
        rows = await conn.fetch(
            """
            SELECT time, event_type, connector_id, payload
            FROM ocpp_events
            WHERE cp_id = $1
              AND ($2::timestamptz IS NULL OR time >= $2)
              AND ($3::timestamptz IS NULL OR time <= $3)
              AND ($4::text IS NULL OR event_type = $4)
            ORDER BY time DESC LIMIT $5
            """,
            cp_id, frm, to, event_type, limit,
        )
    return schemas.TelemetryResponse(
        events=[
            schemas.TelemetryEvent(
                time=r["time"], event_type=r["event_type"],
                connector_id=r["connector_id"],
                payload=_decode_jsonb(r["payload"]),
            )
            for r in rows
        ]
    )


async def get_sessions(
    pool: asyncpg.Pool, org_id: UUID, cp_id: str,
    frm: datetime | None, to: datetime | None, page: int, limit: int,
) -> schemas.SessionListResponse:
    async with pool.acquire() as conn:
        ok = await conn.fetchval(
            "SELECT 1 FROM chargers WHERE cp_id=$1 AND org_id=$2", cp_id, org_id,
        )
        if not ok:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "charger not found")
        total = await conn.fetchval(
            """
            SELECT count(*) FROM charger_sessions
            WHERE cp_id = $1
              AND ($2::timestamptz IS NULL OR started_at >= $2)
              AND ($3::timestamptz IS NULL OR started_at <= $3)
            """,
            cp_id, frm, to,
        )
        offset = (page - 1) * limit
        rows = await conn.fetch(
            """
            SELECT id, connector_id, id_tag, meter_start, meter_stop,
                   energy_kwh, duration_min, stop_reason, started_at, stopped_at
            FROM charger_sessions
            WHERE cp_id = $1
              AND ($2::timestamptz IS NULL OR started_at >= $2)
              AND ($3::timestamptz IS NULL OR started_at <= $3)
            ORDER BY started_at DESC LIMIT $4 OFFSET $5
            """,
            cp_id, frm, to, limit, offset,
        )
    return schemas.SessionListResponse(
        sessions=[schemas.SessionOut(**dict(r)) for r in rows], total=total,
    )


async def send_command(
    redis_client, cp_id: str, req: "schemas.CommandRequest",
) -> "schemas.CommandResponse":
    """Publish an OCPP command to the gateway via Redis and await its reply."""
    import asyncio, json, uuid
    request_id = str(uuid.uuid4())
    stream = f"stream:commands:{cp_id}"
    reply_stream = f"stream:command_replies:{cp_id}"

    last_id = "$"  # only future replies
    await redis_client.xadd(
        stream,
        {
            "request_id": request_id,
            "action": req.command,
            "params": json.dumps(req.params),
        },
        maxlen=1000, approximate=True,
    )
    # Block up to 5s waiting for the matching reply.
    deadline = asyncio.get_event_loop().time() + 5.0
    while asyncio.get_event_loop().time() < deadline:
        remaining = max(100, int((deadline - asyncio.get_event_loop().time()) * 1000))
        resp = await redis_client.xread({reply_stream: last_id}, count=10, block=remaining)
        for _, messages in resp or []:
            for msg_id, fields in messages:
                last_id = msg_id
                if fields.get("request_id") == request_id:
                    payload = json.loads(fields.get("payload", "{}"))
                    return schemas.CommandResponse(
                        status="ok" if payload.get("ok") else "error",
                        request_id=request_id,
                        response=payload.get("response"),
                        error=payload.get("error"),
                    )
    return schemas.CommandResponse(
        status="timeout", request_id=request_id, error="no reply within 5s",
    )


async def bulk_import(
    pool: asyncpg.Pool, org_id: UUID, rows: list["schemas.BulkImportRow"],
) -> "schemas.BulkImportResponse":
    skipped: list[dict[str, str]] = []
    created = 0
    async with pool.acquire() as conn:
        cap = await conn.fetchval(
            "SELECT max_chargers FROM organisations WHERE id = $1", org_id,
        )
        used = await conn.fetchval(
            "SELECT count(*) FROM chargers WHERE org_id = $1", org_id,
        )
        for row in rows:
            if used >= cap:
                skipped.append({"cp_id": row.cp_id, "reason": "quota reached"})
                continue
            exists = await conn.fetchval(
                "SELECT 1 FROM chargers WHERE cp_id = $1", row.cp_id,
            )
            if exists:
                skipped.append({"cp_id": row.cp_id, "reason": "cp_id already exists"})
                continue
            loc_sql = "NULL"
            params: list = [
                row.cp_id, org_id, row.display_name, row.vendor, row.model,
                row.connector_count, row.address, row.city, row.state, row.pincode,
            ]
            if row.lat is not None and row.lng is not None:
                params.extend([row.lng, row.lat])
                loc_sql = f"ST_SetSRID(ST_MakePoint(${len(params)-1}, ${len(params)}), 4326)::geography"
            try:
                await conn.execute(
                    f"""
                    INSERT INTO chargers (
                        cp_id, org_id, display_name, vendor, model, connector_count,
                        address, city, state, pincode, location
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, {loc_sql})
                    """,
                    *params,
                )
                created += 1
                used += 1
            except Exception as exc:
                skipped.append({"cp_id": row.cp_id, "reason": str(exc)[:200]})
    return schemas.BulkImportResponse(created=created, skipped=skipped)


def _decode_jsonb(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return {"raw": value}
    return value or {}
