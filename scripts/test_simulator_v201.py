"""OCPP 2.0.1 simulator: Boot → Status → Heartbeats → TransactionEvent(Started/Updated/Ended).

Usage:
    .venv/bin/python scripts/test_simulator_v201.py [cp_id]
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

import websockets
from ocpp.v201 import ChargePoint as CP, call


class SimCP201(CP):
    pass


async def main(cp_id: str = "CP-V201-001"):
    url = f"ws://localhost:9000/ocpp/{cp_id}"
    print(f"Connecting (ocpp2.0.1) to {url}")
    async with websockets.connect(url, subprotocols=["ocpp2.0.1"]) as ws:
        cp = SimCP201(cp_id, ws)
        listener = asyncio.create_task(cp.start())
        await asyncio.sleep(0.3)

        print("→ BootNotification")
        r = await cp.call(call.BootNotification(
            charging_station={
                "vendor_name": "ABB",
                "model": "Terra-184",
                "firmware_version": "2.1.4",
                "serial_number": "ABB-2026-001",
            },
            reason="PowerUp",
        ))
        print(f"  ← {r}")

        print("→ StatusNotification(Available)")
        await cp.call(call.StatusNotification(
            timestamp=datetime.now(timezone.utc).isoformat(),
            connector_status="Available", evse_id=1, connector_id=1,
        ))

        for i in range(3):
            print(f"→ Heartbeat {i+1}")
            await cp.call(call.Heartbeat())
            await asyncio.sleep(1)

        # Transaction lifecycle
        tx_id = str(uuid.uuid4())
        meter_start = [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sampled_value": [{"value": 1000, "measurand": "Energy.Active.Import.Register",
                               "unit_of_measure": {"unit": "Wh"}}],
        }]
        print(f"→ TransactionEvent(Started) tx={tx_id[:8]}…")
        await cp.call(call.TransactionEvent(
            event_type="Started",
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger_reason="Authorized", seq_no=0,
            transaction_info={"transaction_id": tx_id, "charging_state": "Charging"},
            meter_value=meter_start,
            evse={"id": 1, "connector_id": 1},
            id_token={"id_token": "USER-V201", "type": "Central"},
        ))

        meter_update = [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sampled_value": [
                {"value": 1250, "measurand": "Energy.Active.Import.Register",
                 "unit_of_measure": {"unit": "Wh"}},
                {"value": 231.5, "measurand": "Voltage", "unit_of_measure": {"unit": "V"}},
                {"value": 16.0, "measurand": "Current.Import", "unit_of_measure": {"unit": "A"}},
            ],
        }]
        print("→ TransactionEvent(Updated)")
        await cp.call(call.TransactionEvent(
            event_type="Updated",
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger_reason="MeterValuePeriodic", seq_no=1,
            transaction_info={"transaction_id": tx_id, "charging_state": "Charging"},
            meter_value=meter_update,
            evse={"id": 1, "connector_id": 1},
        ))

        await asyncio.sleep(1)
        meter_stop = [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sampled_value": [{"value": 1500, "measurand": "Energy.Active.Import.Register",
                               "unit_of_measure": {"unit": "Wh"}}],
        }]
        print("→ TransactionEvent(Ended)")
        await cp.call(call.TransactionEvent(
            event_type="Ended",
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger_reason="EVCommunicationLost", seq_no=2,
            transaction_info={"transaction_id": tx_id, "charging_state": "EVConnected",
                              "stopped_reason": "EVDisconnected"},
            meter_value=meter_stop,
            evse={"id": 1, "connector_id": 1},
        ))

        await asyncio.sleep(0.5)
        listener.cancel()
        print("Done.")


if __name__ == "__main__":
    cp_id = sys.argv[1] if len(sys.argv) > 1 else "CP-V201-001"
    asyncio.run(main(cp_id))
