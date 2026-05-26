"""Real-time WebSocket feed for the dashboard.

Clients connect to /api/v1/ws/live?token=<jwt>. The server:
  - validates the token, extracts org_id
  - subscribes the client to a per-org broadcast channel
  - a background task tails Redis incident streams and pushes matching events

Phase-3 scope: incident events + simple status pings. Anomaly + health updates
hook into the same machinery in Week 4.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from uuid import UUID

import redis.asyncio as redis_async
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.security import decode_token
from app.config import get_settings
from app.db.session import get_pool

log = logging.getLogger("chargepulse.ws")

router = APIRouter(tags=["ws"])

# org_id -> set of connected sockets
_clients: dict[UUID, set[WebSocket]] = defaultdict(set)
_tail_task: asyncio.Task | None = None


async def _broadcast(org_id: UUID, message: dict) -> None:
    dead = []
    for ws in _clients.get(org_id, set()):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients[org_id].discard(ws)


async def _tail_incident_streams() -> None:
    settings = get_settings()
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    last_ids: dict[str, str] = {}
    log.info("WS incident tailer started")
    try:
        while True:
            try:
                # Discover all incident streams.
                streams: list[str] = []
                async for k in redis.scan_iter(match="stream:incidents:*", count=100):
                    streams.append(k)
                    last_ids.setdefault(k, "$")  # only future messages by default
                if not streams:
                    await asyncio.sleep(2)
                    continue
                resp = await redis.xread(
                    {s: last_ids[s] for s in streams},
                    count=32, block=5000,
                )
                for stream_name, messages in resp or []:
                    for msg_id, fields in messages:
                        last_ids[stream_name] = msg_id
                        try:
                            org_id = UUID(fields["org_id"])
                            await _broadcast(org_id, {
                                "type": "incident",
                                "incident_id": fields["incident_id"],
                                "cp_id": fields["cp_id"],
                                "severity": fields["severity"],
                                "failure_type": fields.get("failure_type"),
                                "title": fields["title"],
                                "timestamp": fields["detected_at"],
                            })
                        except Exception:
                            log.exception("ws broadcast failed")
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("incident tail loop error")
                await asyncio.sleep(2)
    finally:
        await redis.aclose()


def ensure_tail_task() -> None:
    global _tail_task
    if _tail_task is None or _tail_task.done():
        _tail_task = asyncio.create_task(_tail_incident_streams(), name="ws-tail")


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = decode_token(token)
        org_id = UUID(payload["org_id"])
    except (ValueError, KeyError):
        await websocket.close(code=4401, reason="invalid token")
        return

    await websocket.accept()
    ensure_tail_task()
    _clients[org_id].add(websocket)
    log.info("WS connected org=%s clients=%d", org_id, len(_clients[org_id]))
    try:
        await websocket.send_json({"type": "hello", "org_id": str(org_id)})
        while True:
            # Keep the connection open. We don't expect client messages but
            # consume them to detect disconnects.
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _clients[org_id].discard(websocket)
        log.info("WS disconnected org=%s clients=%d", org_id, len(_clients[org_id]))
