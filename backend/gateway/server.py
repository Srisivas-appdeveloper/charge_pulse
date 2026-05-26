"""OCPP WebSocket gateway entrypoint.

Listens on OCPP_GATEWAY_PORT, negotiates the OCPP subprotocol, instantiates a
per-charger handler, and runs the heartbeat watchdog as a background task.
"""
from __future__ import annotations

import asyncio
import logging

import redis.asyncio as redis_async
import websockets
from websockets.server import WebSocketServerProtocol

from app.config import get_settings
from app.db.session import create_asyncpg_pool

from .command_consumer import CommandConsumer
from .handler_v16 import ChargePulseCP16
from .handler_v201 import ChargePulseCP201
from .heartbeat_watchdog import HeartbeatWatchdog
from .message_router import MessageRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.gateway")

SUPPORTED_SUBPROTOCOLS = ["ocpp1.6", "ocpp2.0.1"]

# cp_id -> connected handler. Used by the watchdog and ensures one connection per CP.
# Both v1.6 and v2.0.1 handlers share the same `id`, `org_id`, `last_heartbeat`
# attributes, so a single dict serves them.
_connected: dict[str, object] = {}


async def handle_connection(
    websocket: WebSocketServerProtocol,
    router: MessageRouter,
    heartbeat_interval: int,
) -> None:
    path = websocket.path
    cp_id = path.strip("/").split("/")[-1]
    subprotocol = websocket.subprotocol

    if not cp_id:
        log.warning("Reject: empty cp_id, path=%s", path)
        await websocket.close(code=1008, reason="cp_id required")
        return

    org_id = await router.lookup_org(cp_id)
    if org_id is None:
        log.warning("Reject %s: not registered", cp_id)
        await websocket.close(code=1008, reason="charger not registered")
        return

    if cp_id in _connected:
        log.warning("Replacing existing connection for %s", cp_id)
        try:
            await _connected[cp_id]._connection.close()
        except Exception:
            pass

    if subprotocol == "ocpp2.0.1":
        cp = ChargePulseCP201(
            cp_id=cp_id, connection=websocket, org_id=org_id,
            router=router, heartbeat_interval=heartbeat_interval,
        )
    else:
        cp = ChargePulseCP16(
            cp_id=cp_id, connection=websocket, org_id=org_id,
            router=router, heartbeat_interval=heartbeat_interval,
        )
    _connected[cp_id] = cp
    log.info("Charger connected: %s (subprotocol=%s)", cp_id, subprotocol)

    try:
        await cp.start()
    except websockets.exceptions.ConnectionClosed as exc:
        log.info("Charger %s disconnected: %s", cp_id, exc)
    except Exception:
        log.exception("Handler crashed for %s", cp_id)
    finally:
        _connected.pop(cp_id, None)
        await router.mark_offline(cp_id)
        await router.publish(
            cp_id=cp_id,
            org_id=org_id,
            event_type="disconnect",
            payload={"reason": "ws_closed"},
        )


async def main() -> None:
    settings = get_settings()
    pg_pool = await create_asyncpg_pool()
    redis_client = redis_async.from_url(
        settings.redis_url, encoding="utf-8", decode_responses=True
    )
    router = MessageRouter(pg_pool, redis_client)
    watchdog = HeartbeatWatchdog(
        _connected, router, settings.ocpp_heartbeat_timeout
    )
    watchdog.start()
    commands = CommandConsumer(_connected, redis_client)
    commands.start()

    async def _handler(ws: WebSocketServerProtocol) -> None:
        await handle_connection(ws, router, settings.ocpp_heartbeat_interval)

    server = await websockets.serve(
        _handler,
        settings.ocpp_gateway_host,
        settings.ocpp_gateway_port,
        subprotocols=SUPPORTED_SUBPROTOCOLS,
        ping_interval=30,
        ping_timeout=10,
    )
    log.info(
        "OCPP gateway listening on %s:%d",
        settings.ocpp_gateway_host,
        settings.ocpp_gateway_port,
    )
    try:
        await server.wait_closed()
    finally:
        await watchdog.stop()
        await commands.stop()
        await redis_client.aclose()
        await pg_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
