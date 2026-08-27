from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ReplyParameters
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.keyboards import anonymous_comment_button, moderation_reply, moderation_submission
from app.models import AnonymousReply, Category, Submission, SubmissionStatus
from app.services.content import send_content
from app.services.store import audit

logger = logging.getLogger(__name__)


async def resolve_bot_username(bot: Bot, settings: Settings) -> str:
    if settings.bot_username:
        return settings.bot_username.lstrip("@")
    me = await bot.get_me()
    if not me.username:
        raise RuntimeError("The Telegram bot must have a username")
    return me.username


async def notify_user(bot: Bot, user_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.info("Could not notify user %s", user_id)


async def send_submission_to_moderation(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    submission: Submission,
) -> None:
    category = await session.get(Category, submission.category_id)
    bot_username = await resolve_bot_username(bot, settings)
    prefix = (
        f"<b>Yangi anonim xabar #{submission.id}</b>\nKategoriya: {category.emoji} {category.title}"
    )
    message = await send_content(
        bot,
        settings.moderation_chat_id,
        content_type=submission.content_type,
        text=submission.text,
        file_id=submission.file_id,
        prefix=prefix,
        reply_markup=moderation_submission(submission.id, bot_username, submission.token),
    )
    submission.moderation_message_id = message.message_id
    await audit(session, None, "submission.queued", "submission", submission.id)


async def publish_submission(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    submission: Submission,
    actor_id: int | None = None,
    send_notification: bool = True,
) -> None:
    if submission.status == SubmissionStatus.PUBLISHED.value:
        return
    category = await session.get(Category, submission.category_id)
    footer = f"{category.emoji} #{category.key} · #{submission.id}"
    message = await send_content(
        bot,
        settings.channel_id,
        content_type=submission.content_type,
        text=submission.text,
        file_id=submission.file_id,
        footer=footer,
    )
    now = datetime.now(UTC)
    submission.status = SubmissionStatus.PUBLISHED.value
    submission.channel_message_id = message.message_id
    submission.reviewer_id = actor_id
    submission.reviewed_at = now
    submission.published_at = now
    await audit(session, actor_id, "submission.published", "submission", submission.id)
    if send_notification:
        await notify_user(
            bot,
            submission.user_id,
            f"✅ <b>#{submission.id}</b> xabaringiz kanalga joylandi.",
        )


async def attach_comment_entry(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    submission: Submission,
    discussion_chat_id: int,
    discussion_message_id: int,
) -> None:
    submission.discussion_chat_id = discussion_chat_id
    submission.discussion_message_id = discussion_message_id
    bot_username = await resolve_bot_username(bot, settings)
    try:
        await bot.send_message(
            discussion_chat_id,
            "Bu postga shaxsingizni ko‘rsatmasdan javob qoldirishingiz mumkin.",
            reply_markup=anonymous_comment_button(bot_username, submission.comment_token),
            reply_parameters=ReplyParameters(message_id=discussion_message_id),
            disable_notification=True,
        )
    except TelegramBadRequest as exc:
        logger.warning("Could not attach anonymous comment button: %s", exc)
        return
    await audit(session, None, "submission.comment_linked", "submission", submission.id)


async def send_reply_to_moderation(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    reply: AnonymousReply,
) -> None:
    prefix = f"<b>Yangi anonim komment #{reply.id}</b>\nKanal posti: #{reply.submission_id}"
    message = await send_content(
        bot,
        settings.moderation_chat_id,
        content_type=reply.content_type,
        text=reply.text,
        file_id=reply.file_id,
        prefix=prefix,
        reply_markup=moderation_reply(reply.id),
    )
    reply.moderation_message_id = message.message_id
    await audit(session, None, "reply.queued", "anonymous_reply", reply.id)


async def publish_reply(
    session: AsyncSession,
    bot: Bot,
    reply: AnonymousReply,
    actor_id: int | None = None,
    send_notification: bool = True,
) -> None:
    submission = await session.get(Submission, reply.submission_id)
    if not submission or not submission.discussion_chat_id or not submission.discussion_message_id:
        raise RuntimeError("The channel post is not linked to its discussion message yet")
    if reply.status == SubmissionStatus.PUBLISHED.value:
        return
    message = await send_content(
        bot,
        submission.discussion_chat_id,
        content_type=reply.content_type,
        text=reply.text,
        file_id=reply.file_id,
        prefix="<b>Anonim javob</b>",
        footer=f"#anonim_{reply.id}",
        reply_to_message_id=submission.discussion_message_id,
    )
    now = datetime.now(UTC)
    reply.status = SubmissionStatus.PUBLISHED.value
    reply.discussion_message_id = message.message_id
    reply.reviewer_id = actor_id
    reply.reviewed_at = now
    reply.published_at = now
    await audit(session, actor_id, "reply.published", "anonymous_reply", reply.id)
    if send_notification:
        await notify_user(
            bot,
            reply.user_id,
            f"✅ Anonim javobingiz <b>#{submission.id}</b>-post kommentiga joylandi.",
        )
