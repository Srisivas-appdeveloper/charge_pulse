"""Alert worker.

Consumes `stream:incidents:*` and dispatches to every alert_config matching the
org + severity threshold.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async

from app.alerts.dispatcher import dispatch
from app.config import get_settings
from app.db.session import create_asyncpg_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.alert_worker")

CONSUMER_GROUP = "alert_dispatcher"
CONSUMER_NAME = "worker-1"

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


async def ensure_group(redis: redis_async.Redis, key: str) -> None:
    try:
        await redis.xgroup_create(key, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def list_incident_streams(redis: redis_async.Redis) -> list[str]:
    keys: list[str] = []
    async for k in redis.scan_iter(match="stream:incidents:*", count=100):
        keys.append(k)
    return keys


async def handle(pool: asyncpg.Pool, fields: dict) -> None:
    incident_id = UUID(fields["incident_id"])
    org_id = UUID(fields["org_id"])
    severity = fields["severity"]

    async with pool.acquire() as conn:
        incident = await conn.fetchrow(
            """
            SELECT id, cp_id, severity, failure_type, title, description,
                   anomaly_score, detected_at
            FROM incidents WHERE id = $1
            """,
            incident_id,
        )
        charger = await conn.fetchrow(
            "SELECT cp_id, display_name, address, city, state FROM chargers "
            "WHERE cp_id = $1",
            fields["cp_id"],
        )
        configs = await conn.fetch(
            "SELECT channel, endpoint, severity_min FROM alert_configs "
            "WHERE org_id = $1 AND is_active = true",
            org_id,
        )

    if not incident or not charger or not configs:
        return

    inc_rank = _SEVERITY_RANK.get(severity, 0)
    incident_dict = dict(incident)
    charger_dict = dict(charger)
    for c in configs:
        if _SEVERITY_RANK.get(c["severity_min"], 0) > inc_rank:
            continue
        ok = await dispatch(
            c["channel"], c["endpoint"],
            incident=incident_dict, charger=charger_dict,
        )
        log.info(
            "Alert dispatch incident=%s channel=%s ok=%s",
            incident_id, c["channel"], ok,
        )


async def main() -> None:
    settings = get_settings()
    pool = await create_asyncpg_pool()
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    log.info("Alert worker started")
    try:
        while True:
            try:
                streams = await list_incident_streams(redis)
                if not streams:
                    await asyncio.sleep(5)
                    continue
                for s in streams:
                    await ensure_group(redis, s)
                resp = await redis.xreadgroup(
                    CONSUMER_GROUP, CONSUMER_NAME,
                    {s: ">" for s in streams},
                    count=32, block=5000,
                )
                for stream_name, messages in resp or []:
                    for msg_id, fields in messages:
                        try:
                            await handle(pool, fields)
                        except Exception:
                            log.exception("alert failed msg=%s", msg_id)
                        finally:
                            await redis.xack(stream_name, CONSUMER_GROUP, msg_id)
            except Exception:
                log.exception("alert loop error")
                await asyncio.sleep(2)
    finally:
        await redis.aclose()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
