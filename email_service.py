"""
email_service.py - Brevo (Sendinblue) transactional email sending
Uses plain httpx (no heavy SDK) to keep RAM low.
"""
from __future__ import annotations

import logging
import textwrap
from typing import Optional

import httpx

from config import BREVO_API_KEY, SENDER_EMAIL, SENDER_NAME

log = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"

_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=15.0,
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
    return _client


async def close_http_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()


def _build_html(body_text: str) -> str:
    """Wrap plain-text body in a minimal, clean HTML email shell."""
    # Convert newlines to <br> and wrap in HTML
    html_body = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html_body = html_body.replace("\n", "<br>\n")
    return textwrap.dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width,initial-scale=1">
          <style>
            body {{font-family:Arial,Helvetica,sans-serif;font-size:15px;
                   color:#222;background:#fff;margin:0;padding:20px}}
            .wrap {{max-width:600px;margin:0 auto}}
            p {{line-height:1.6;margin:0 0 12px}}
          </style>
        </head>
        <body>
          <div class="wrap">
            <p>{html_body}</p>
          </div>
        </body>
        </html>
    """)


async def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
) -> tuple[bool, str]:
    """
    Send a single email via Brevo.
    Returns (success: bool, message: str).
    """
    html_content = _build_html(body_text)
    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
        "textContent": body_text,
        "replyTo": {"email": SENDER_EMAIL, "name": SENDER_NAME},
        "headers": {
            "X-Mailer": "ColdEmailBot/1.0",
        },
    }

    try:
        client = get_http_client()
        resp = await client.post(BREVO_URL, json=payload)
        if resp.status_code in (200, 201):
            log.info("Email sent → %s (%s)", to_email, to_name)
            return True, "OK"
        else:
            msg = f"Brevo {resp.status_code}: {resp.text[:300]}"
            log.warning("Email failed → %s | %s", to_email, msg)
            return False, msg
    except httpx.RequestError as exc:
        msg = f"Network error: {exc}"
        log.error("Email error → %s | %s", to_email, msg)
        return False, msg


async def check_brevo_inbox(
    page: int = 1,
    limit: int = 20,
) -> list[dict]:
    """
    Poll Brevo transactional events for replies.
    Brevo doesn't expose raw replies, so we check the 'events' endpoint
    for inbound activity.  Full reply detection requires an inbound domain
    or webhook – this polls for recent events.
    """
    try:
        client = get_http_client()
        resp = await client.get(
            "https://api.brevo.com/v3/smtp/statistics/events",
            params={"event": "reply", "limit": limit, "offset": (page - 1) * limit},
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("events", [])
        log.warning("Inbox poll failed: %s %s", resp.status_code, resp.text[:200])
        return []
    except Exception as exc:
        log.error("Inbox poll error: %s", exc)
        return []
