"""Detects silent disconnects.

If a connected charger hasn't sent a Heartbeat (or any message) within
OCPP_HEARTBEAT_TIMEOUT seconds, mark it offline and publish a disconnect event.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .handler_v16 import ChargePulseCP16
    from .message_router import MessageRouter

log = logging.getLogger("chargepulse.gateway.watchdog")

CHECK_INTERVAL_SEC = 30


class HeartbeatWatchdog:
    def __init__(
        self,
        connected: dict[str, "ChargePulseCP16"],
        router: "MessageRouter",
        timeout_sec: int,
    ):
        self.connected = connected
        self.router = router
        self.timeout = timeout_sec
        self._stale_marked: set[str] = set()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="heartbeat-watchdog")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        log.info("Watchdog started (timeout=%ss)", self.timeout)
        while True:
            try:
                await asyncio.sleep(CHECK_INTERVAL_SEC)
                await self._scan()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Watchdog scan failed")

    async def _scan(self) -> None:
        now = datetime.now(timezone.utc)
        for cp_id, cp in list(self.connected.items()):
            age = (now - cp.last_heartbeat).total_seconds()
            if age > self.timeout and cp_id not in self._stale_marked:
                log.warning("Charger %s silent for %.0fs — marking offline", cp_id, age)
                await self.router.mark_offline(cp_id)
                await self.router.publish(
                    cp_id=cp_id,
                    org_id=cp.org_id,
                    event_type="disconnect",
                    payload={"reason": "heartbeat_timeout", "silent_for_sec": age},
                    ts=now,
                )
                self._stale_marked.add(cp_id)
            elif age <= self.timeout and cp_id in self._stale_marked:
                self._stale_marked.discard(cp_id)

    def forget(self, cp_id: str) -> None:
        self._stale_marked.discard(cp_id)
