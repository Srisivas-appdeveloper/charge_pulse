"""Inference worker (Phase 1: rules-only).

Consumes `stream:features:*` from Redis. For each new feature vector, evaluates
the rule engine. Each firing rule becomes a row in `incidents` and a message on
`stream:incidents:{cp_id}` for the alert worker.

When ML models land in Week 4, this worker will also load the per-charger LSTM
autoencoder and write anomaly_score / is_anomaly back into feature_vectors.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis_async

from app.config import get_settings
from app.db.session import create_asyncpg_pool
from ml import rules
from ml.inference import load_active_model, score_latest_window, write_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.inference_worker")

CONSUMER_GROUP = "inference_engine"
CONSUMER_NAME = "worker-1"
DEDUP_WINDOW_MIN = 60


async def ensure_group(redis: redis_async.Redis, key: str) -> None:
    try:
        await redis.xgroup_create(key, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception as exc:  # group may already exist
        if "BUSYGROUP" not in str(exc):
            raise


async def list_feature_streams(redis: redis_async.Redis) -> list[str]:
    keys: list[str] = []
    async for k in redis.scan_iter(match="stream:features:*", count=100):
        keys.append(k)
    return keys


async def handle_message(
    pool: asyncpg.Pool, redis: redis_async.Redis,
    cp_id: str, fields: dict,
) -> None:
    feats = json.loads(fields["features"])
    org_id = fields["org_id"]
    window_end_str = fields.get("window_end")

    # --- ML scoring (if a trained model exists for this charger) ---
    anomaly_score: float | None = None
    ml_is_anomaly = False
    scorer = await load_active_model(pool, cp_id)
    if scorer:
        try:
            result = await score_latest_window(pool, scorer, cp_id)
            if result:
                anomaly_score = float(result["anomaly_score"])
                ml_is_anomaly = bool(result["is_anomaly"])
                await write_score(
                    pool, cp_id, result["scored_at"],
                    anomaly_score, ml_is_anomaly,
                )
        except Exception:
            log.exception("ML scoring failed cp=%s", cp_id)

    # --- Rule evaluation (always runs as a guardrail) ---
    fired = rules.evaluate(feats)

    # If ML flagged an anomaly but no rule fired, create an ML-detected incident.
    if ml_is_anomaly and not fired:
        async with pool.acquire() as conn:
            incident = await conn.fetchrow(
                """
                INSERT INTO incidents
                  (cp_id, org_id, severity, failure_type, title, description,
                   anomaly_score, auto_detected)
                VALUES ($1, $2, 'medium', 'unknown', $3, $4, $5, true)
                RETURNING id, severity, failure_type, title, detected_at
                """,
                cp_id, org_id,
                "Anomalous behaviour detected",
                f"LSTM autoencoder anomaly_score={anomaly_score:.4f} > threshold "
                f"on window ending {window_end_str}",
                anomaly_score,
            )
        await redis.xadd(
            f"stream:incidents:{cp_id}",
            {
                "incident_id": str(incident["id"]),
                "cp_id": cp_id,
                "org_id": org_id,
                "severity": incident["severity"],
                "failure_type": incident["failure_type"] or "",
                "title": incident["title"],
                "detected_at": incident["detected_at"].isoformat(),
            },
            maxlen=10_000, approximate=True,
        )
        log.info("ML incident created cp=%s score=%.4f", cp_id, anomaly_score)

    if not fired:
        return

    now = datetime.now(timezone.utc)
    for rule in fired:
        async with pool.acquire() as conn:
            # Deduplicate: don't reopen identical incidents within the last hour.
            dup = await conn.fetchval(
                """
                SELECT id FROM incidents
                WHERE cp_id = $1 AND failure_type = $2
                  AND resolved_at IS NULL
                  AND detected_at > $3
                ORDER BY detected_at DESC LIMIT 1
                """,
                cp_id, rule.failure_type, now.replace(microsecond=0),
            )
            if dup:
                continue
            incident = await conn.fetchrow(
                """
                INSERT INTO incidents
                  (cp_id, org_id, severity, failure_type, title, description,
                   anomaly_score, auto_detected)
                VALUES ($1, $2, $3, $4, $5, $6, $7, true)
                RETURNING id, severity, failure_type, title, detected_at
                """,
                cp_id, org_id, rule.severity, rule.failure_type, rule.title,
                f"Rule '{rule.name}' fired on window ending {window_end_str}",
                anomaly_score,
            )
        await redis.xadd(
            f"stream:incidents:{cp_id}",
            {
                "incident_id": str(incident["id"]),
                "cp_id": cp_id,
                "org_id": org_id,
                "severity": incident["severity"],
                "failure_type": incident["failure_type"] or "",
                "title": incident["title"],
                "detected_at": incident["detected_at"].isoformat(),
            },
            maxlen=10_000, approximate=True,
        )
        log.info(
            "Incident created cp=%s rule=%s severity=%s",
            cp_id, rule.name, rule.severity,
        )


async def main() -> None:
    settings = get_settings()
    pool = await create_asyncpg_pool()
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    log.info("Inference worker started (rules-only)")
    try:
        while True:
            try:
                streams = await list_feature_streams(redis)
                if not streams:
                    await asyncio.sleep(5)
                    continue
                for s in streams:
                    await ensure_group(redis, s)
                resp = await redis.xreadgroup(
                    CONSUMER_GROUP, CONSUMER_NAME,
                    {s: ">" for s in streams},
                    count=64, block=5000,
                )
                for stream_name, messages in resp or []:
                    cp_id = stream_name.rsplit(":", 1)[-1]
                    for msg_id, fields in messages:
                        try:
                            await handle_message(pool, redis, cp_id, fields)
                        except Exception:
                            log.exception("inference failed msg=%s", msg_id)
                        finally:
                            await redis.xack(stream_name, CONSUMER_GROUP, msg_id)
            except Exception:
                log.exception("inference loop error")
                await asyncio.sleep(2)
    finally:
        await redis.aclose()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
