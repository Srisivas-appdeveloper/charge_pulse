"""Simulate a misbehaving charger to trip a rule.

Sends a Faulted StatusNotification, then sits — the feature worker will compute
`time_in_faulted_pct > 0.10` and the inference worker will create a critical
'connector_fault' incident.
"""
import asyncio
from datetime import datetime, timezone

import websockets
from ocpp.v16 import ChargePoint as CP, call


class SimCP(CP):
    pass


async def main(cp_id: str = "CP001"):
    url = f"ws://localhost:9000/ocpp/{cp_id}"
    async with websockets.connect(url, subprotocols=["ocpp1.6"]) as ws:
        cp = SimCP(cp_id, ws)
        listener = asyncio.create_task(cp.start())
        await asyncio.sleep(0.3)

        print("→ BootNotification")
        await cp.call(call.BootNotification(
            charge_point_vendor="Delta", charge_point_model="DC-60kW",
            firmware_version="1.2.3",
        ))

        print("→ StatusNotification(Faulted)")
        await cp.call(call.StatusNotification(
            connector_id=1, error_code="GroundFailure", status="Faulted",
        ))

        # Keep the WS open so the Faulted state persists across the 1-min window.
        print("Holding connection 75s to span a feature window...")
        for i in range(15):
            await asyncio.sleep(5)
            await cp.call(call.Heartbeat())
            print(f"  hb {i+1}")

        listener.cancel()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
