"""Multi-channel alert dispatcher.

Each channel uses its own transport:
  - sms      → MSG91 flow API
  - whatsapp → Meta WhatsApp Cloud API
  - email    → SMTP (SES-compatible)
  - webhook  → POST JSON
  - slack    → POST to incoming webhook URL with block format
"""
from __future__ import annotations

import logging
import os
from email.message import EmailMessage
from typing import Any

import aiosmtplib
import httpx

log = logging.getLogger("chargepulse.alerts")


def render_message(incident: dict[str, Any], charger: dict[str, Any]) -> str:
    return (
        "🔴 ChargePulse Alert\n\n"
        f"Charger: {charger.get('display_name') or charger['cp_id']} ({charger['cp_id']})\n"
        f"Location: {charger.get('address') or '-'}\n"
        f"Severity: {incident['severity']}\n"
        f"Issue: {incident['title']}\n"
        f"Score: {incident.get('anomaly_score') or '-'}\n"
        f"Detected: {incident['detected_at'].isoformat()}\n\n"
        f"View: https://app.chargepulse.in/incidents/{incident['id']}"
    )


async def dispatch(
    channel: str, endpoint: str, *,
    incident: dict[str, Any], charger: dict[str, Any],
) -> bool:
    body = render_message(incident, charger)
    try:
        if channel == "email":
            return await _send_email(endpoint, incident["title"], body)
        if channel == "sms":
            return await _send_sms(endpoint, body)
        if channel == "whatsapp":
            return await _send_whatsapp(endpoint, body)
        if channel == "webhook":
            return await _send_webhook(endpoint, incident, charger)
        if channel == "slack":
            return await _send_slack(endpoint, body)
    except Exception:
        log.exception("Alert dispatch failed channel=%s endpoint=%s", channel, endpoint)
        return False
    log.warning("Unknown alert channel: %s", channel)
    return False


async def _send_email(to: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host:
        log.warning("SMTP_HOST not set; skipping email")
        return False
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "alerts@chargepulse.in")
    msg["To"] = to
    msg["Subject"] = f"[ChargePulse] {subject}"
    msg.set_content(body)
    await aiosmtplib.send(
        msg,
        hostname=host,
        port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USER"),
        password=os.getenv("SMTP_PASSWORD"),
        start_tls=True,
    )
    return True


async def _send_sms(phone: str, body: str) -> bool:
    key = os.getenv("MSG91_AUTH_KEY")
    if not key:
        log.warning("MSG91_AUTH_KEY not set; skipping SMS")
        return False
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.msg91.com/api/v5/flow/",
            headers={"authkey": key, "content-type": "application/json"},
            json={
                "template_id": os.getenv("MSG91_TEMPLATE_ID"),
                "sender": os.getenv("MSG91_SENDER_ID", "CHGPLS"),
                "recipients": [{"mobiles": phone, "var": body[:160]}],
            },
        )
        r.raise_for_status()
    return True


async def _send_whatsapp(phone: str, body: str) -> bool:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        log.warning("WhatsApp creds missing; skipping")
        return False
    base = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v18.0")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{base}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": body},
            },
        )
        r.raise_for_status()
    return True


async def _send_webhook(url: str, incident: dict, charger: dict) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json={
            "type": "incident",
            "incident": {**incident, "id": str(incident["id"]),
                         "detected_at": incident["detected_at"].isoformat()},
            "charger": charger,
        })
        r.raise_for_status()
    return True


async def _send_slack(webhook_url: str, body: str) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(webhook_url, json={
            "blocks": [{
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{body}```"},
            }],
        })
        r.raise_for_status()
    return True
