from datetime import UTC, datetime, timedelta

from app.models import User
from app.security import (
    content_fingerprint,
    make_token,
    requires_review,
    user_is_banned,
    valid_token,
)


def test_deep_link_token_is_safe() -> None:
    for _ in range(50):
        token = make_token()
        assert valid_token(token)
        assert 8 <= len(token) <= 32


def test_fingerprint_normalizes_text() -> None:
    first = content_fingerprint("text", "  Salom   DUNYO ", None)
    second = content_fingerprint("text", "salom dunyo", None)
    assert first == second


def test_hybrid_review_rule() -> None:
    assert requires_review("Sayt: https://example.com", [])
    assert requires_review("Bu yerda reklama bor", ["reklama"])
    assert not requires_review("Oddiy talabalar savoli", ["reklama"])


def test_temporary_ban_expires() -> None:
    user = User(telegram_id=1, anon_code="ABC12345", is_banned=True)
    user.banned_until = datetime.now(UTC) - timedelta(seconds=1)
    assert not user_is_banned(user)
    user.banned_until = datetime.now(UTC) + timedelta(minutes=1)
    assert user_is_banned(user)
