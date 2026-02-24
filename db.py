"""
db.py - MongoDB Atlas async client (motor)
All database operations live here.  Nothing else talks to Mongo directly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import motor.motor_asyncio
from pymongo import ASCENDING, IndexModel

from config import MONGO_URI, MONGO_DB_NAME
from models import utcnow, validate_email

log = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────
_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None


def get_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=5,       # keep RAM low
            minPoolSize=1,
        )
    return _client


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return get_client()[MONGO_DB_NAME]


# ── Index bootstrap (call once at startup) ────────────────────────────────────
async def ensure_indexes() -> None:
    db = get_db()
    await db.leads.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("niche_tag", ASCENDING)]),
        IndexModel([("used", ASCENDING)]),
        IndexModel([("replied", ASCENDING)]),
    ])
    await db.templates.create_indexes([
        IndexModel([("niche_tag", ASCENDING)], unique=True),
    ])
    await db.blacklist.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True),
    ])
    log.info("MongoDB indexes ensured.")


# ─────────────────────────────── LEADS ───────────────────────────────────────

async def insert_lead(name: str, email: str, niche_tag: str) -> dict:
    """Insert a single lead. Returns (doc, is_new)."""
    db = get_db()
    email = validate_email(email)
    doc = {
        "name": name.strip(),
        "email": email,
        "niche_tag": niche_tag.strip().lower(),
        "used": False,
        "replied": False,
        "template_used": None,
        "sent_at": None,
        "failed": False,
        "fail_count": 0,
        "created_at": utcnow(),
    }
    # Check blacklist first
    if await db.blacklist.find_one({"email": email}):
        raise ValueError(f"Email {email} is blacklisted.")
    # Upsert to avoid duplicates
    result = await db.leads.update_one(
        {"email": email},
        {"$setOnInsert": doc},
        upsert=True,
    )
    is_new = result.upserted_id is not None
    return {"doc": doc, "is_new": is_new}


async def remove_leads(emails: list[str]) -> int:
    db = get_db()
    emails = [validate_email(e) for e in emails]
    result = await db.leads.delete_many({"email": {"$in": emails}})
    return result.deleted_count


async def get_unsent_leads(niche_tag: str) -> list[dict]:
    db = get_db()
    cursor = db.leads.find({
        "niche_tag": niche_tag.strip().lower(),
        "used": False,
        "replied": False,
        "failed": False,
    })
    return await cursor.to_list(length=None)


async def mark_lead_sent(email: str, template_used: str) -> None:
    db = get_db()
    await db.leads.update_one(
        {"email": email},
        {"$set": {
            "used": True,
            "template_used": template_used,
            "sent_at": utcnow(),
            "failed": False,
            "fail_count": 0,
        }},
    )


async def mark_lead_failed(email: str) -> None:
    db = get_db()
    await db.leads.update_one(
        {"email": email},
        {"$inc": {"fail_count": 1}, "$set": {"failed": True}},
    )


async def mark_lead_replied(email: str) -> Optional[dict]:
    db = get_db()
    lead = await db.leads.find_one({"email": email})
    if lead:
        await db.leads.update_one(
            {"email": email},
            {"$set": {"replied": True}},
        )
    return lead


async def manual_mark_replied(email: str) -> bool:
    db = get_db()
    email = validate_email(email)
    result = await db.leads.update_one(
        {"email": email},
        {"$set": {"replied": True}},
    )
    return result.modified_count > 0


async def get_stats() -> dict:
    db = get_db()
    total = await db.leads.count_documents({})
    sent  = await db.leads.count_documents({"used": True})
    replied = await db.leads.count_documents({"replied": True})
    remaining = await db.leads.count_documents({"used": False, "replied": False, "failed": False})
    failed = await db.leads.count_documents({"failed": True})
    reply_rate = round((replied / sent * 100), 1) if sent else 0.0
    return {
        "total": total,
        "sent": sent,
        "replied": replied,
        "remaining": remaining,
        "failed": failed,
        "reply_rate": reply_rate,
    }


async def get_leads_for_export(niche_tag: Optional[str] = None) -> list[dict]:
    db = get_db()
    query: dict[str, Any] = {}
    if niche_tag:
        query["niche_tag"] = niche_tag.strip().lower()
    cursor = db.leads.find(query, {"_id": 0})
    return await cursor.to_list(length=None)


async def get_retry_leads(niche_tag: str) -> list[dict]:
    """Leads that failed and haven't exceeded max retries."""
    from config import MAX_RETRIES
    db = get_db()
    cursor = db.leads.find({
        "niche_tag": niche_tag.strip().lower(),
        "failed": True,
        "fail_count": {"$lt": MAX_RETRIES},
        "used": False,
    })
    return await cursor.to_list(length=None)


# ─────────────────────────────── TEMPLATES ───────────────────────────────────

async def upsert_template(niche_tag: str, subject: str, body: str) -> None:
    db = get_db()
    await db.templates.update_one(
        {"niche_tag": niche_tag.strip().lower()},
        {"$set": {
            "subject": subject.strip(),
            "body": body.strip(),
            "created_at": utcnow(),
        }},
        upsert=True,
    )


async def get_template(niche_tag: str) -> Optional[dict]:
    db = get_db()
    return await db.templates.find_one({"niche_tag": niche_tag.strip().lower()})


async def remove_template(niche_tag: str) -> bool:
    db = get_db()
    result = await db.templates.delete_one({"niche_tag": niche_tag.strip().lower()})
    return result.deleted_count > 0


async def list_templates() -> list[dict]:
    db = get_db()
    cursor = db.templates.find({}, {"_id": 0, "niche_tag": 1, "subject": 1})
    return await cursor.to_list(length=None)


# ─────────────────────────────── BLACKLIST ────────────────────────────────────

async def add_to_blacklist(email: str, reason: str = "manual") -> bool:
    db = get_db()
    email = validate_email(email)
    result = await db.blacklist.update_one(
        {"email": email},
        {"$setOnInsert": {"email": email, "reason": reason, "created_at": utcnow()}},
        upsert=True,
    )
    # Also mark the lead as used so it won't be sent again
    await db.leads.update_one({"email": email}, {"$set": {"used": True}})
    return result.upserted_id is not None


async def remove_from_blacklist(email: str) -> bool:
    db = get_db()
    email = validate_email(email)
    result = await db.blacklist.delete_one({"email": email})
    return result.deleted_count > 0


async def list_blacklist() -> list[str]:
    db = get_db()
    cursor = db.blacklist.find({}, {"_id": 0, "email": 1})
    docs = await cursor.to_list(length=None)
    return [d["email"] for d in docs]


# ─────────────────────────────── DAILY COUNTER ───────────────────────────────

async def get_daily_sent_count() -> int:
    """Count emails sent today (UTC)."""
    db = get_db()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return await db.leads.count_documents({"sent_at": {"$gte": today_start}})
