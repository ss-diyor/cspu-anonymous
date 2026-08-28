from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import RateLimitBucket

logger = logging.getLogger("security.rate_limit")


def _actor_hash(telegram_id: int | None, secret: str) -> str:
    if telegram_id is None:
        return "system"
    return hmac.new(secret.encode(), str(telegram_id).encode(), hashlib.sha256).hexdigest()[:20]


async def consume_limit(
    session: AsyncSession,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> int:
    now = datetime.now(UTC)
    bucket = await session.get(RateLimitBucket, key, with_for_update=True)
    if bucket is None:
        try:
            async with session.begin_nested():
                session.add(RateLimitBucket(key=key, count=1, window_started_at=now))
                await session.flush()
            return 0
        except IntegrityError:
            # A parallel request created the bucket after our first SELECT.
            bucket = await session.get(RateLimitBucket, key, with_for_update=True)
            if bucket is None:
                return 0

    started = bucket.window_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    reset_at = started + timedelta(seconds=window_seconds)
    if now >= reset_at:
        bucket.count = 1
        bucket.window_started_at = now
        return 0
    if bucket.count >= limit:
        return max(1, int((reset_at - now).total_seconds()) + 1)
    bucket.count += 1
    return 0


class TelegramRateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def __call__(self, handler, event: Update, data):
        telegram_id: int | None = None
        response_target: Message | CallbackQuery | None = None
        if event.callback_query:
            telegram_id = event.callback_query.from_user.id
            response_target = event.callback_query
        elif event.message and event.message.from_user:
            telegram_id = event.message.from_user.id
            response_target = event.message

        async with self.session_factory() as db, db.begin():
            global_retry = await consume_limit(
                db,
                "updates:global",
                limit=self.settings.global_update_limit,
                window_seconds=self.settings.rate_limit_window_seconds,
            )
            user_retry = 0
            if telegram_id is not None:
                actor_key = _actor_hash(telegram_id, self.settings.webhook_secret)
                user_retry = await consume_limit(
                    db,
                    f"updates:user:{actor_key}",
                    limit=self.settings.user_update_limit,
                    window_seconds=self.settings.rate_limit_window_seconds,
                )
        retry_after = max(global_retry, user_retry)
        if not retry_after:
            return await handler(event, data)

        logger.warning(
            "rate_limit_exceeded user=%s retry_after=%s",
            _actor_hash(telegram_id, self.settings.webhook_secret),
            retry_after,
        )
        if isinstance(response_target, CallbackQuery):
            await response_target.answer(
                f"Juda ko‘p so‘rov. {retry_after} soniyadan keyin qayta urinib ko‘ring.",
                show_alert=True,
            )
        elif isinstance(response_target, Message) and telegram_id is not None:
            await response_target.answer(
                f"Juda ko‘p so‘rov. {retry_after} soniyadan keyin qayta urinib ko‘ring."
            )
        return None
