"""
models.py - Pydantic models & pure Python dataclasses (no heavy ODM)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, field_validator


EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]+$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError(f"Invalid email address: {email}")
    return email


# ── MongoDB document shapes (used when reading from DB) ───────────────────────

class Lead(BaseModel):
    name: str
    email: str
    niche_tag: str
    used: bool = False
    replied: bool = False
    template_used: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime = utcnow()
    failed: bool = False
    fail_count: int = 0

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email(v)

    @field_validator("name", "niche_tag")
    @classmethod
    def strip_strings(cls, v: str) -> str:
        return v.strip()


class Template(BaseModel):
    niche_tag: str
    subject: str
    body: str
    created_at: datetime = utcnow()

    @field_validator("niche_tag", "subject", "body")
    @classmethod
    def strip_strings(cls, v: str) -> str:
        return v.strip()


class BlacklistEntry(BaseModel):
    email: str
    reason: Optional[str] = "manual"
    created_at: datetime = utcnow()

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email(v)


# ── Conversation state keys (stored in bot context) ───────────────────────────

class ConvState:
    IDLE = "idle"
    # /add flow
    ADD_LEADS_WAITING_PAIRS = "add_leads_waiting_pairs"
    ADD_LEADS_WAITING_TAG = "add_leads_waiting_tag"
    # /addtemplate flow
    TMPL_WAITING_TAG = "tmpl_waiting_tag"
    TMPL_WAITING_SUBJECT = "tmpl_waiting_subject"
    TMPL_WAITING_BODY = "tmpl_waiting_body"
