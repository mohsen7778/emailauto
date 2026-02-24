"""
main.py - FastAPI entrypoint.
Runs both the FastAPI server and the Telegram bot in the same process
using shared asyncio event loop (lightweight, no second process).

Brevo inbound webhook:  POST /webhook/reply
Health check:          GET  /health
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

import db
from config import LOG_LEVEL, PORT, TELEGRAM_BOT_TOKEN
from telegram_bot import build_application, process_inbound_reply, set_commands
from email_service import close_http_client

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# Global reference to PTB application
_tg_app = None


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tg_app
    log.info("Starting up …")

    # 1. MongoDB indexes
    await db.ensure_indexes()

    # 2. Build and start Telegram bot (polling in background task)
    _tg_app = build_application()
    await _tg_app.initialize()
    await set_commands(_tg_app)
    await _tg_app.start()
    await _tg_app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    log.info("Telegram bot started (polling).")

    yield  # ── app is running ──

    # Shutdown
    log.info("Shutting down …")
    await _tg_app.updater.stop()
    await _tg_app.stop()
    await _tg_app.shutdown()
    await close_http_client()
    db.get_client().close()
    log.info("Shutdown complete.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cold Email Bot API",
    version="1.0.0",
    docs_url=None,       # disable Swagger in prod (saves RAM)
    redoc_url=None,
    lifespan=lifespan,
)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    try:
        # Quick ping to confirm Mongo is alive
        await db.get_client().admin.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return JSONResponse({"status": "ok", "mongo": mongo_ok})


# ── Brevo inbound webhook ─────────────────────────────────────────────────────
@app.post("/webhook/reply")
async def brevo_reply_webhook(request: Request):
    """
    Brevo sends a POST here when an email is received on your inbound domain.
    Payload is multipart/form-data or JSON depending on configuration.
    We parse both.
    """
    global _tg_app
    content_type = request.headers.get("content-type", "")

    try:
        if "application/json" in content_type:
            data: dict[str, Any] = await request.json()
        else:
            # Brevo sends multipart for inbound
            form = await request.form()
            data = dict(form)
    except Exception as exc:
        log.error("Webhook parse error: %s", exc)
        raise HTTPException(status_code=400, detail="Bad payload")

    # Extract fields from Brevo inbound payload
    sender = data.get("sender", "") or data.get("From", "")
    # sender might be "Name <email>" format
    sender_name, sender_email = _parse_sender(str(sender))

    subject      = str(data.get("subject", data.get("Subject", "(no subject)")))
    text_preview = str(data.get("text", data.get("plain", "")))[:400]

    log.info("Inbound reply from %s <%s>", sender_name, sender_email)

    if _tg_app and sender_email:
        await process_inbound_reply(
            _tg_app,
            sender_email,
            sender_name,
            subject,
            text_preview,
        )

    return JSONResponse({"status": "received"})


def _parse_sender(raw: str) -> tuple[str, str]:
    """Parse 'Name <email@domain.com>' into (name, email)."""
    import re
    m = re.search(r"<([^>]+)>", raw)
    if m:
        email = m.group(1).strip().lower()
        name = raw[:m.start()].strip().strip('"').strip("'")
    else:
        email = raw.strip().lower()
        name = ""
    return name, email


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL.lower(),
        workers=1,          # single worker = lower RAM
        loop="asyncio",
    )
