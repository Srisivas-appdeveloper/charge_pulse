"""Multi-charger OCPP simulator with realistic load + injectable faults.

Usage:
    .venv/bin/python scripts/simulate_charger.py --count 5 --duration 300
    .venv/bin/python scripts/simulate_charger.py --cp_ids CP001,CP002 --fault voltage_low
"""
import argparse
import asyncio
import random
from datetime import datetime, timezone

import websockets
from ocpp.v16 import ChargePoint as CP, call

GATEWAY = "ws://localhost:9000/ocpp"


class SimCP(CP):
    pass


async def steady_meter_burst(cp: SimCP, connector_id: int, transaction_id: int,
                             *, voltage_low: bool = False) -> None:
    voltage = 190 if voltage_low else round(random.uniform(225, 235), 1)
    await cp.call(call.MeterValues(
        connector_id=connector_id, transaction_id=transaction_id,
        meter_value=[{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sampled_value": [
                {"value": str(random.randint(800, 1200)), "measurand": "Energy.Active.Import.Register", "unit": "Wh"},
                {"value": str(voltage), "measurand": "Voltage", "unit": "V"},
                {"value": str(round(random.uniform(15, 25), 1)), "measurand": "Current.Import", "unit": "A"},
                {"value": str(round(random.uniform(18, 25), 1)), "measurand": "Power.Active.Import", "unit": "kW"},
            ],
        }],
    ))


async def run_one(cp_id: str, duration: int, fault: str | None) -> None:
    url = f"{GATEWAY}/{cp_id}"
    try:
        async with websockets.connect(url, subprotocols=["ocpp1.6"]) as ws:
            cp = SimCP(cp_id, ws)
            listener = asyncio.create_task(cp.start())
            await asyncio.sleep(0.2)

            vendors = ["Delta", "ABB", "Exicom", "Servotech"]
            await cp.call(call.BootNotification(
                charge_point_vendor=random.choice(vendors),
                charge_point_model="DC-60kW",
                firmware_version="1.4.0",
            ))
            await cp.call(call.StatusNotification(
                connector_id=1, error_code="NoError",
                status="Faulted" if fault == "faulted" else "Available",
            ))
            print(f"[{cp_id}] connected")

            tx_id: int | None = None
            elapsed = 0
            while elapsed < duration:
                # Heartbeat every 5s
                await cp.call(call.Heartbeat())
                if tx_id is None and random.random() < 0.3:
                    r = await cp.call(call.StartTransaction(
                        connector_id=1, id_tag=f"USER-{random.randint(100,999)}",
                        meter_start=random.randint(1000, 50000),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
                    tx_id = r.transaction_id
                    print(f"[{cp_id}] tx started {tx_id}")
                elif tx_id is not None:
                    await steady_meter_burst(cp, 1, tx_id, voltage_low=fault == "voltage_low")
                    if random.random() < 0.15:  # ~5 min sessions
                        reason = "PowerLoss" if fault == "power_loss" else "EVDisconnected"
                        await cp.call(call.StopTransaction(
                            transaction_id=tx_id,
                            meter_stop=random.randint(60000, 80000),
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            reason=reason,
                        ))
                        print(f"[{cp_id}] tx stopped ({reason})")
                        tx_id = None
                await asyncio.sleep(5)
                elapsed += 5

            listener.cancel()
            print(f"[{cp_id}] done")
    except Exception as exc:
        print(f"[{cp_id}] FAILED: {exc}")


async def main(cp_ids: list[str], duration: int, fault: str | None) -> None:
    await asyncio.gather(*(run_one(cp, duration, fault) for cp in cp_ids))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3, help="number of CP-SIM-* chargers if --cp_ids not given")
    ap.add_argument("--cp_ids", default=None, help="comma-separated cp_ids")
    ap.add_argument("--duration", type=int, default=120, help="run time in seconds")
    ap.add_argument("--fault", choices=["voltage_low", "faulted", "power_loss"], default=None)
    args = ap.parse_args()
    cps = args.cp_ids.split(",") if args.cp_ids else [f"CP-SIM-{i:03d}" for i in range(1, args.count + 1)]
    asyncio.run(main(cps, args.duration, args.fault))
