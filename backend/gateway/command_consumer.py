"""Bridges API → gateway. Consumes `stream:commands:{cp_id}` and dispatches
OCPP requests to the matching connected ChargePoint instance.

The API never holds WebSocket connections directly; instead it XADDs a command
onto Redis. This worker reads commands, looks up the live cp, calls the right
ocpp method, and (when ack requested) XADDs the response onto
`stream:command_replies:{cp_id}`.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import redis.asyncio as redis_async
from ocpp.v16 import call as call_v16
from ocpp.v201 import call as call_v201

if TYPE_CHECKING:
    from .handler_v16 import ChargePulseCP16
    from .handler_v201 import ChargePulseCP201

log = logging.getLogger("chargepulse.gateway.commands")

CONSUMER_GROUP = "gateway_dispatch"
CONSUMER_NAME = "gw-1"


SUPPORTED_V16 = {
    "Reset": lambda p: call_v16.Reset(type=p.get("type", "Soft")),
    "TriggerMessage": lambda p: call_v16.TriggerMessage(
        requested_message=p["requested_message"],
        connector_id=p.get("connector_id"),
    ),
    "ChangeConfiguration": lambda p: call_v16.ChangeConfiguration(
        key=p["key"], value=p["value"],
    ),
    "GetDiagnostics": lambda p: call_v16.GetDiagnostics(location=p["location"]),
    "RemoteStartTransaction": lambda p: call_v16.RemoteStartTransaction(
        connector_id=p.get("connector_id", 1), id_tag=p["id_tag"],
    ),
    "RemoteStopTransaction": lambda p: call_v16.RemoteStopTransaction(
        transaction_id=p["transaction_id"],
    ),
}

SUPPORTED_V201 = {
    "Reset": lambda p: call_v201.Reset(
        type=p.get("type", "OnIdle"), evse_id=p.get("evse_id"),
    ),
    "RequestStartTransaction": lambda p: call_v201.RequestStartTransaction(
        id_token={"id_token": p["id_token"], "type": p.get("id_token_type", "Central")},
        remote_start_id=int(p.get("remote_start_id", 1)),
        evse_id=p.get("evse_id", 1),
    ),
    "RequestStopTransaction": lambda p: call_v201.RequestStopTransaction(
        transaction_id=p["transaction_id"],
    ),
    "ChangeAvailability": lambda p: call_v201.ChangeAvailability(
        operational_status=p.get("operational_status", "Inoperative"),
        evse=p.get("evse"),
    ),
}


class CommandConsumer:
    def __init__(
        self,
        connected: dict[str, "ChargePulseCP16"],
        redis: redis_async.Redis,
    ):
        self.connected = connected
        self.redis = redis
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="cmd-consumer")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _ensure_group(self, stream: str) -> None:
        try:
            await self.redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def _run(self) -> None:
        log.info("Command consumer started")
        while True:
            try:
                streams: list[str] = []
                async for k in self.redis.scan_iter(match="stream:commands:*", count=100):
                    streams.append(k)
                    await self._ensure_group(k)
                if not streams:
                    await asyncio.sleep(2)
                    continue
                resp = await self.redis.xreadgroup(
                    CONSUMER_GROUP, CONSUMER_NAME,
                    {s: ">" for s in streams},
                    count=16, block=5000,
                )
                for stream_name, messages in resp or []:
                    cp_id = stream_name.rsplit(":", 1)[-1]
                    for msg_id, fields in messages:
                        try:
                            await self._dispatch(cp_id, msg_id, fields)
                        finally:
                            await self.redis.xack(stream_name, CONSUMER_GROUP, msg_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Command consumer loop error")
                await asyncio.sleep(2)

    async def _dispatch(self, cp_id: str, msg_id: str, fields: dict) -> None:
        action = fields.get("action")
        params = json.loads(fields.get("params", "{}"))
        request_id = fields.get("request_id", msg_id)

        cp = self.connected.get(cp_id)
        if cp is None:
            await self._reply(cp_id, request_id, ok=False, error="charger not connected")
            return

        # Pick the right call builder based on the connected handler's protocol.
        is_v201 = type(cp).__name__ == "ChargePulseCP201"
        builder = (SUPPORTED_V201 if is_v201 else SUPPORTED_V16).get(action)
        if builder is None:
            proto = "ocpp2.0.1" if is_v201 else "ocpp1.6"
            await self._reply(cp_id, request_id, ok=False,
                              error=f"action '{action}' not supported on {proto}")
            return

        try:
            payload = builder(params)
            response = await cp.call(payload)
            await self._reply(
                cp_id, request_id, ok=True,
                response=_to_serialisable(response),
            )
            log.info("Command sent cp=%s action=%s protocol=%s",
                     cp_id, action, "v2.0.1" if is_v201 else "v1.6")
        except Exception as exc:
            log.exception("Command failed cp=%s action=%s", cp_id, action)
            await self._reply(cp_id, request_id, ok=False, error=str(exc))

    async def _reply(self, cp_id: str, request_id: str, **payload) -> None:
        await self.redis.xadd(
            f"stream:command_replies:{cp_id}",
            {"request_id": request_id, "payload": json.dumps(payload, default=str)},
            maxlen=1000, approximate=True,
        )


def _to_serialisable(obj):
    if hasattr(obj, "__dict__"):
        return {k: _to_serialisable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serialisable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_serialisable(v) for k, v in obj.items()}
    return obj
