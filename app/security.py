from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime

from app.models import User

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")
URL_RE = re.compile(r"(?:https?://|t\.me/|www\.)", re.IGNORECASE)


def make_token(length: int = 12) -> str:
    token = secrets.token_urlsafe(length)
    return token[: min(32, max(8, length * 4 // 3))]


def make_anon_code() -> str:
    return secrets.token_hex(4).upper()


def valid_token(token: str) -> bool:
    return bool(TOKEN_RE.fullmatch(token))


def content_fingerprint(content_type: str, text: str | None, file_unique_id: str | None) -> str:
    normalized = " ".join((text or "").lower().split())
    raw = f"{content_type}\0{normalized}\0{file_unique_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def user_is_banned(user: User, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if not user.is_banned:
        return False
    if user.banned_until and user.banned_until <= now:
        return False
    return True


def requires_review(text: str | None, banned_words: list[str]) -> bool:
    value = (text or "").casefold()
    if URL_RE.search(value):
        return True
    return any(word.casefold().strip() in value for word in banned_words if word.strip())
