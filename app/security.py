from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import User

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")
URL_RE = re.compile(
    r"(?:https?://|www\.|t\.me(?:/|(?=\s|$))|telegram\.me(?:/|(?=\s|$))|"
    r"(?:[a-z0-9-]+\.)+(?:uz|com|org|net|ru|io|me)(?=[/\s.,!?;:)]|$))",
    re.IGNORECASE,
)
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
NON_ALNUM_RE = re.compile(r"[^\w]+", re.UNICODE)
REPEATED_RE = re.compile(r"(.)\1{2,}")

# Common Cyrillic characters attackers use inside otherwise Latin words.
CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "ё": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "к": "k",
        "м": "m",
        "т": "t",
        "в": "b",
        "н": "h",
        "і": "i",
        "ј": "j",
    }
)


@dataclass(frozen=True, slots=True)
class ReviewResult:
    reasons: tuple[str, ...] = ()
    matched_words: tuple[str, ...] = ()

    @property
    def required(self) -> bool:
        return bool(self.reasons or self.matched_words)


def make_token(length: int = 12) -> str:
    token = secrets.token_urlsafe(length)
    return token[: min(32, max(8, length * 4 // 3))]


def make_anon_code() -> str:
    return secrets.token_hex(8).upper()


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


def normalize_for_filter(value: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = ZERO_WIDTH_RE.sub("", normalized).translate(CONFUSABLES)
    normalized = REPEATED_RE.sub(r"\1", normalized)
    spaced = " ".join(NON_ALNUM_RE.sub(" ", normalized).split())
    compact = NON_ALNUM_RE.sub("", normalized)
    return spaced, compact


def inspect_content(text: str | None, banned_words: list[str]) -> ReviewResult:
    raw = text or ""
    spaced, compact = normalize_for_filter(raw)
    reasons: list[str] = []
    if URL_RE.search(unicodedata.normalize("NFKC", raw).casefold()):
        reasons.append("link")

    matches: list[str] = []
    for raw_word in banned_words:
        word = raw_word.strip()
        if not word:
            continue
        word_spaced, word_compact = normalize_for_filter(word)
        if not word_compact:
            continue
        boundary_match = bool(re.search(rf"(?<!\w){re.escape(word_spaced)}(?!\w)", spaced))
        compact_match = len(word_compact) >= 4 and word_compact in compact
        if boundary_match or compact_match:
            matches.append(word)
    return ReviewResult(tuple(dict.fromkeys(reasons)), tuple(dict.fromkeys(matches)))


def parse_banned_words(value: str) -> list[str]:
    parts = re.split(r"[,;\n\r]+", value)
    words = [" ".join(part.strip().split()) for part in parts]
    return list(dict.fromkeys(word for word in words if word))


def requires_review(text: str | None, banned_words: list[str]) -> bool:
    return inspect_content(text, banned_words).required
