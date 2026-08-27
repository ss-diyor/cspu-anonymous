from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import Submission, SubmissionStatus
from app.services.publishing import attach_comment_entry

router = Router(name="discussion")


@router.message(F.is_automatic_forward == True)  # noqa: E712
async def automatic_channel_forward(
    message: Message,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    if message.chat.id != settings.discussion_chat_id:
        return
    origin = message.forward_origin
    channel_message_id = getattr(origin, "message_id", None)
    origin_chat = getattr(origin, "chat", None)
    if not channel_message_id or not origin_chat or origin_chat.id != settings.channel_id:
        return
    # Telegram may deliver the discussion auto-forward before the publish transaction commits.
    # A short bounded retry prevents losing the anonymous-reply button in that race.
    for attempt in range(6):
        async with session_factory() as db, db.begin():
            submission = await db.scalar(
                select(Submission).where(
                    Submission.channel_message_id == channel_message_id,
                    Submission.status == SubmissionStatus.PUBLISHED.value,
                )
            )
            if submission:
                if submission.discussion_message_id:
                    return
                await attach_comment_entry(
                    db,
                    bot,
                    settings,
                    submission,
                    message.chat.id,
                    message.message_id,
                )
                return
        if attempt < 5:
            await asyncio.sleep(0.4)
