"""Persists OCPP events to TimescaleDB and publishes them to Redis Streams.

Every incoming OCPP message becomes one row in `ocpp_events` and one entry in
`stream:ocpp:{cp_id}`. Downstream workers (feature engine, alert engine) consume
from Redis; the DB is the durable archive.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async

STREAM_MAXLEN = 100_000


class MessageRouter:
    def __init__(self, pg_pool: asyncpg.Pool, redis_client: redis_async.Redis):
        self.pg = pg_pool
        self.redis = redis_client

    async def publish(
        self,
        *,
        cp_id: str,
        org_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        connector_id: int | None = None,
        raw_frame: dict[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> None:
        ts = ts or datetime.now(timezone.utc)
        payload_json = json.dumps(payload, default=str)
        raw_json = json.dumps(raw_frame, default=str) if raw_frame else None

        async with self.pg.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ocpp_events
                  (time, cp_id, org_id, event_type, connector_id, payload, raw_frame)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                """,
                ts, cp_id, org_id, event_type, connector_id, payload_json, raw_json,
            )

        await self.redis.xadd(
            f"stream:ocpp:{cp_id}",
            {
                "cp_id": cp_id,
                "org_id": str(org_id),
                "event_type": event_type,
                "connector_id": str(connector_id) if connector_id is not None else "",
                "ts": ts.isoformat(),
                "payload": payload_json,
            },
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )

    async def record_session_start(
        self,
        *,
        cp_id: str,
        org_id: UUID,
        connector_id: int,
        id_tag: str,
        meter_start: int,
        started_at: datetime,
    ) -> int:
        """Insert a session row and return a generated transaction_id."""
        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO charger_sessions
                  (time, cp_id, org_id, connector_id, id_tag,
                   meter_start, started_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                started_at, cp_id, org_id, connector_id, id_tag,
                meter_start, started_at,
            )
            await conn.execute(
                "UPDATE chargers SET last_session_at = $1, updated_at = now() "
                "WHERE cp_id = $2",
                started_at, cp_id,
            )
        # Transaction IDs in OCPP are signed 32-bit ints. Use the session row id
        # truncated to fit.
        return int(row["id"]) % 2**31

    async def record_session_stop(
        self,
        *,
        cp_id: str,
        transaction_id: int,
        meter_stop: int,
        stopped_at: datetime,
        stop_reason: str | None,
    ) -> None:
        async with self.pg.acquire() as conn:
            # Match by truncated id since transaction_id was derived from row id.
            await conn.execute(
                """
                UPDATE charger_sessions
                   SET meter_stop = $1,
                       stopped_at = $2,
                       stop_reason = $3,
                       duration_min = EXTRACT(EPOCH FROM ($2 - started_at)) / 60.0,
                       energy_kwh = GREATEST($1 - meter_start, 0) / 1000.0
                 WHERE cp_id = $4
                   AND (id % 2147483648) = $5
                   AND stopped_at IS NULL
                """,
                meter_stop, stopped_at, stop_reason, cp_id, transaction_id,
            )

    async def upsert_charger_on_boot(
        self,
        *,
        cp_id: str,
        org_id: UUID,
        vendor: str | None,
        model: str | None,
        firmware: str | None,
        serial: str | None,
        boot_at: datetime,
    ) -> None:
        async with self.pg.acquire() as conn:
            await conn.execute(
                """
                UPDATE chargers
                   SET vendor = COALESCE($1, vendor),
                       model = COALESCE($2, model),
                       firmware_version = COALESCE($3, firmware_version),
                       serial_number = COALESCE($4, serial_number),
                       last_boot_at = $5,
                       status = 'online',
                       updated_at = now()
                 WHERE cp_id = $6
                """,
                vendor, model, firmware, serial, boot_at, cp_id,
            )

    async def update_heartbeat(self, cp_id: str, ts: datetime) -> None:
        async with self.pg.acquire() as conn:
            await conn.execute(
                "UPDATE chargers SET last_heartbeat_at = $1, status = 'online', "
                "updated_at = now() WHERE cp_id = $2",
                ts, cp_id,
            )

    async def update_status(
        self,
        cp_id: str,
        normalized_status: str,
        error_code: str,
    ) -> None:
        new_status = "faulted" if normalized_status.lower() == "faulted" else "online"
        async with self.pg.acquire() as conn:
            await conn.execute(
                "UPDATE chargers SET status = $1, updated_at = now() "
                "WHERE cp_id = $2",
                new_status, cp_id,
            )

    async def mark_offline(self, cp_id: str) -> None:
        async with self.pg.acquire() as conn:
            await conn.execute(
                "UPDATE chargers SET status = 'offline', updated_at = now() "
                "WHERE cp_id = $1",
                cp_id,
            )

    async def lookup_org(self, cp_id: str) -> UUID | None:
        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT org_id FROM chargers WHERE cp_id = $1", cp_id,
            )
            return row["org_id"] if row else None
