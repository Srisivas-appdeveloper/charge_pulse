# CPO onboarding — ChargePulse

Pointing your charging fleet at ChargePulse takes under 30 minutes for a typical
50-charger pilot. This is the operator-facing checklist.

---

## 1 · What you'll need

- A list of your chargers as a CSV (sample at [`scripts/sample_chargers.csv`](scripts/sample_chargers.csv))
- Admin access to your CSMS / charger config portal (Delta, ABB, Exicom, etc.)
- An email for the ChargePulse account owner
- Optional: a Slack/webhook URL for incident alerts

## 2 · Prepare the CSV

Required columns:

| column | example | notes |
|---|---|---|
| `cp_id` | `CP-CHN-001` | Must match the `chargePointId` the charger sends in its OCPP `BootNotification` |
| `display_name` | `Anna Salai DC-1` | Human-readable label shown in the dashboard |
| `vendor` | `Delta` | One of `Delta`, `ABB`, `Exicom`, `Servotech`, or your manufacturer name |
| `model` | `DC-60kW` | Model code |
| `city` | `Chennai` | Plain text |
| `state` | `TN` | 2-letter code |
| `pincode` | `600002` | Indian PIN |
| `lat` / `lng` | `13.0732` / `80.2609` | Decimal degrees (for the fleet map) |
| `connector_count` | `1` | Defaults to 1 |

## 3 · Bulk-import the chargers

```bash
.venv/bin/python scripts/seed_demo_data.py \
  --org "ChargeZone Chennai" \
  --email cto@chargezone.in --password 'use-a-real-password' \
  --csv scripts/sample_chargers.csv \
  --webhook https://hooks.slack.com/services/XXX/YYY
```

The script will:
1. Register the org (or log in if it already exists)
2. Bulk-import every row from the CSV
3. Set up a default **email** alert channel (severity ≥ high)
4. Set up an optional **webhook** alert channel (severity ≥ medium)
5. Print the WebSocket URL each charger should point to

## 4 · Configure the chargers

For each row, log into the charger's web UI or push a remote config and set the
CSMS URL:

```
ws://csms.chargepulse.in/ocpp/<cp_id>
```

(Use `wss://` in production with SSL termination at nginx — see the deployment guide.)

Recommended OCPP settings (these are also tuned per-vendor automatically once a
charger boots):

| key | value |
|---|---|
| `HeartbeatInterval` | `60` |
| `MeterValueSampleInterval` | `30` |
| `MeterValuesSampledData` | `Energy.Active.Import.Register,Voltage,Current.Import,Power.Active.Import` |
| `WebSocketPingInterval` | `30` |

## 5 · Watch chargers come online

- Sign in at `https://app.chargepulse.in`
- Within 60s of each charger booting, it should appear on the Dashboard with
  status `online` and its vendor/firmware populated.
- The Fleet Map will pin chargers with valid lat/lng.

## 6 · Tune alerts (optional)

Open **Alert Config** and add channels:

| channel | endpoint | use |
|---|---|---|
| `email` | `oncall@your-cpo.in` | Inbox / paging |
| `sms` | `+91XXXXXXXXXX` | MSG91 SMS |
| `whatsapp` | `+91XXXXXXXXXX` | WhatsApp business |
| `webhook` | your endpoint | Internal ticketing |
| `slack` | Slack incoming-webhook URL | Team channel |

Default severity threshold is `medium`; set higher to reduce noise during pilot.

## 7 · Verify end-to-end (recommended before going live)

Run the simulator against one of your registered `cp_id`s to make sure
events flow:

```bash
.venv/bin/python scripts/simulate_charger.py --cp_ids CP-CHN-001 --duration 180
```

You should see, in real time:
- The dashboard counter ticking up
- Telemetry events on the Charger Detail page
- New session rows after the simulator runs a transaction

## 8 · Going live

A few minutes after the first hour of live traffic, train the LSTM autoencoder
for any high-priority chargers so they start getting ML-based anomaly scoring:

```bash
cd backend
../.venv/bin/python -m ml.training.train_anomaly --cp_id CP-CHN-001 --days 14
```

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Charger never appears online | Wrong `cp_id` in CSV — must match what charger sends |
| Gateway rejects connection (1008) | `cp_id` not registered in DB |
| Heartbeats arrive but no MeterValues | Sample interval too high or measurand list missing |
| Status stuck "offline" | Charger's WebSocket pings disabled; bump `WebSocketPingInterval` |
| Alerts not firing | Severity threshold too high, or alert config marked inactive |
