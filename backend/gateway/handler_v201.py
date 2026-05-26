"""OCPP 2.0.1 handler.

Normalises v2.0.1 messages into the same `event_type` shape that the v1.6
pipeline produces. Downstream (feature engine, rules, ML, alerts) is protocol-
agnostic — it just sees `boot`, `heartbeat`, `status`, `meter`, `tx_start`,
`tx_stop`, `authorize`, `disconnect`.

Key v1.6 → v2.0.1 mapping:
  StatusNotification     → still StatusNotification (slightly different fields)
  StartTransaction       → TransactionEvent(event_type=Started)
  StopTransaction        → TransactionEvent(event_type=Ended)
  MeterValues (in-tx)    → TransactionEvent(meter_value=...)
  MeterValues (out-of-tx)→ MeterValues
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from ocpp.routing import on
from ocpp.v201 import ChargePoint as CP201
from ocpp.v201 import call_result
from ocpp.v201.enums import RegistrationStatusEnumType

from .message_router import MessageRouter
from .vendor_profiles import VendorProfile, resolve

log = logging.getLogger("chargepulse.gateway.v201")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ChargePulseCP201(CP201):
    def __init__(
        self,
        cp_id: str,
        connection,
        org_id: UUID,
        router: MessageRouter,
        heartbeat_interval: int,
    ):
        super().__init__(cp_id, connection)
        self.org_id = org_id
        self.router = router
        self.heartbeat_interval = heartbeat_interval
        self.vendor_profile: VendorProfile = resolve(None)
        self.connected_at = _now()
        self.last_heartbeat = self.connected_at
        # Map OCPP v2.0.1 string transactionId → our int session id (so v2.0.1
        # incidents/sessions look identical in the dashboard to v1.6 ones).
        self._tx_map: dict[str, int] = {}

    @on("BootNotification")
    async def on_boot(self, charging_station: dict, reason: str, **kwargs):
        vendor = charging_station.get("vendor_name")
        model = charging_station.get("model")
        firmware = charging_station.get("firmware_version")
        serial = charging_station.get("serial_number")
        self.vendor_profile = resolve(vendor)
        boot_at = _now()
        await self.router.upsert_charger_on_boot(
            cp_id=self.id, org_id=self.org_id,
            vendor=vendor, model=model, firmware=firmware, serial=serial,
            boot_at=boot_at,
        )
        await self.router.publish(
            cp_id=self.id, org_id=self.org_id, event_type="boot",
            payload={"vendor": vendor, "model": model, "firmware": firmware,
                     "serial": serial, "reason": reason, "protocol": "ocpp2.0.1"},
            ts=boot_at,
        )
        log.info("Boot %s vendor=%s model=%s reason=%s", self.id, vendor, model, reason)
        return call_result.BootNotification(
            current_time=_now().isoformat(),
            interval=self.vendor_profile.get_heartbeat_interval() or self.heartbeat_interval,
            status=RegistrationStatusEnumType.accepted,
        )

    @on("Heartbeat")
    async def on_heartbeat(self, **kwargs):
        ts = _now()
        self.last_heartbeat = ts
        await self.router.update_heartbeat(self.id, ts)
        await self.router.publish(
            cp_id=self.id, org_id=self.org_id, event_type="heartbeat",
            payload={}, ts=ts,
        )
        return call_result.Heartbeat(current_time=ts.isoformat())

    @on("StatusNotification")
    async def on_status(
        self, timestamp: str, connector_status: str, evse_id: int,
        connector_id: int, **kwargs,
    ):
        normalized = self.vendor_profile.normalize_status(connector_status)
        # v2.0.1 doesn't carry an error_code on StatusNotification — those move
        # to NotifyEvent. Default to NoError unless the status itself is Faulted.
        error_code = "Faulted" if normalized.lower() == "faulted" else "NoError"
        await self.router.update_status(self.id, normalized, error_code)
        await self.router.publish(
            cp_id=self.id, org_id=self.org_id, event_type="status",
            connector_id=connector_id,
            payload={
                "status": normalized, "error_code": error_code,
                "evse_id": evse_id, "raw_status": connector_status,
                "protocol": "ocpp2.0.1",
            },
            ts=_parse_ts(timestamp) or _now(),
        )
        return call_result.StatusNotification()

    @on("MeterValues")
    async def on_meter_values(self, evse_id: int, meter_value: list, **kwargs):
        normalized = self.vendor_profile.normalize_meter_values(meter_value)
        await self.router.publish(
            cp_id=self.id, org_id=self.org_id, event_type="meter",
            connector_id=evse_id,
            payload={"meter_value": normalized, "evse_id": evse_id,
                     "protocol": "ocpp2.0.1"},
        )
        return call_result.MeterValues()

    @on("TransactionEvent")
    async def on_transaction_event(
        self, event_type: str, timestamp: str, trigger_reason: str,
        seq_no: int, transaction_info: dict, **kwargs,
    ):
        """v2.0.1 unifies session lifecycle + per-meter into one message stream.

        Routes:
          Started → tx_start (creates session)
          Updated → meter   (in-tx telemetry)
          Ended   → tx_stop (finalises session)
        """
        ts = _parse_ts(timestamp) or _now()
        tx_id_str = transaction_info.get("transaction_id", "")
        evse = kwargs.get("evse") or {}
        connector_id = evse.get("connector_id") if evse else 1
        meter_value = kwargs.get("meter_value") or []
        id_token = (kwargs.get("id_token") or {}).get("id_token", "anon")

        if event_type == "Started":
            meter_start = _first_energy_wh(meter_value) or 0
            tx_id_int = await self.router.record_session_start(
                cp_id=self.id, org_id=self.org_id,
                connector_id=connector_id, id_tag=id_token,
                meter_start=int(meter_start), started_at=ts,
            )
            self._tx_map[tx_id_str] = tx_id_int
            await self.router.publish(
                cp_id=self.id, org_id=self.org_id, event_type="tx_start",
                connector_id=connector_id,
                payload={"transaction_id": tx_id_int, "id_tag": id_token,
                         "meter_start": meter_start, "trigger_reason": trigger_reason,
                         "protocol": "ocpp2.0.1"},
                ts=ts,
            )
        elif event_type == "Updated":
            await self.router.publish(
                cp_id=self.id, org_id=self.org_id, event_type="meter",
                connector_id=connector_id,
                payload={"transaction_id": self._tx_map.get(tx_id_str),
                         "meter_value": meter_value,
                         "trigger_reason": trigger_reason,
                         "protocol": "ocpp2.0.1"},
                ts=ts,
            )
        elif event_type == "Ended":
            tx_id_int = self._tx_map.pop(tx_id_str, 0)
            meter_stop = _first_energy_wh(meter_value) or 0
            stop_reason = transaction_info.get("stopped_reason") or "EVDisconnected"
            await self.router.record_session_stop(
                cp_id=self.id, transaction_id=tx_id_int,
                meter_stop=int(meter_stop), stopped_at=ts, stop_reason=stop_reason,
            )
            await self.router.publish(
                cp_id=self.id, org_id=self.org_id, event_type="tx_stop",
                payload={"transaction_id": tx_id_int, "meter_stop": meter_stop,
                         "reason": stop_reason, "trigger_reason": trigger_reason,
                         "protocol": "ocpp2.0.1"},
                ts=ts,
            )
        return call_result.TransactionEvent()

    @on("Authorize")
    async def on_authorize(self, id_token: dict, **kwargs):
        await self.router.publish(
            cp_id=self.id, org_id=self.org_id, event_type="authorize",
            payload={"id_token": id_token.get("id_token"),
                     "type": id_token.get("type"), "protocol": "ocpp2.0.1"},
        )
        return call_result.Authorize(id_token_info={"status": "Accepted"})

    @on("NotifyEvent")
    async def on_notify_event(self, generated_at: str, seq_no: int,
                              event_data: list, **kwargs):
        # v2.0.1 reports errors and state changes through NotifyEvent rather than
        # bundling them with StatusNotification — surface them so features can
        # count error_codes the same way.
        for ev in event_data or []:
            await self.router.publish(
                cp_id=self.id, org_id=self.org_id, event_type="notify_event",
                payload={"event": ev, "protocol": "ocpp2.0.1"},
                ts=_parse_ts(generated_at) or _now(),
            )
        return call_result.NotifyEvent()

    @on("DataTransfer")
    async def on_data_transfer(self, vendor_id: str, **kwargs):
        await self.router.publish(
            cp_id=self.id, org_id=self.org_id, event_type="data_transfer",
            payload={"vendor_id": vendor_id,
                     "message_id": kwargs.get("message_id"),
                     "data": kwargs.get("data"), "protocol": "ocpp2.0.1"},
        )
        return call_result.DataTransfer(status="Accepted")

    @on("FirmwareStatusNotification")
    async def on_firmware_status(self, status: str, **kwargs):
        await self.router.publish(
            cp_id=self.id, org_id=self.org_id, event_type="firmware_status",
            payload={"status": status, "protocol": "ocpp2.0.1"},
        )
        return call_result.FirmwareStatusNotification()


def _first_energy_wh(meter_value: list) -> float | None:
    """Pull the first 'Energy.Active.Import.Register'-like reading from a
    v2.0.1 MeterValue list. Used to populate meter_start / meter_stop."""
    for mv in meter_value or []:
        for sv in mv.get("sampled_value", []) or []:
            meas = (sv.get("measurand") or "Energy.Active.Import.Register").strip()
            if "Energy.Active" in meas:
                try:
                    val = float(sv.get("value", 0))
                    unit = (sv.get("unit_of_measure") or {}).get("unit") or sv.get("unit") or "Wh"
                    return val if unit == "Wh" else val * 1000
                except (TypeError, ValueError):
                    continue
    return None
