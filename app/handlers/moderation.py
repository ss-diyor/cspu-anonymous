from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.keyboards import (
    ban_confirmation,
    moderation_reply,
    moderation_submission,
    rejection_reasons,
)
from app.models import AnonymousReply, Submission, SubmissionStatus, User
from app.services.publishing import (
    notify_user,
    publish_reply,
    publish_submission,
    resolve_bot_username,
)
from app.services.store import audit, is_admin

router = Router(name="moderation")

REASONS = {
    "rules": "Qoidalarga zid",
    "abuse": "Haqoratli mazmun",
    "spam": "Reklama yoki spam",
    "personal": "Shaxsiy ma’lumot mavjud",
    "offtopic": "Mavzuga aloqasiz",
    "other": "Moderator qarori",
}


async def _authorized(
    callback: CallbackQuery,
    db: AsyncSession,
    settings: Settings,
) -> bool:
    if await is_admin(db, settings, callback.from_user.id):
        return True
    await callback.answer("Bu amal faqat moderatorlar uchun.", show_alert=True)
    return False


async def _remove_keyboard(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("sub:approve:"))
async def approve_submission(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    submission_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        submission = await db.get(Submission, submission_id, with_for_update=True)
        if not submission or submission.status != SubmissionStatus.PENDING.value:
            await callback.answer("Xabar allaqachon ko‘rib chiqilgan.", show_alert=True)
            return
        try:
            await publish_submission(db, bot, settings, submission, callback.from_user.id)
        except TelegramBadRequest as exc:
            await callback.answer(f"Kanalga yuborilmadi: {exc.message}", show_alert=True)
            return
    await _remove_keyboard(callback)
    await callback.message.reply(f"✅ #{submission_id} tasdiqlandi.")
    await callback.answer("Kanalga joylandi")


@router.callback_query(F.data.startswith("sub:reject:"))
async def choose_submission_rejection(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    submission_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
    await callback.message.edit_reply_markup(reply_markup=rejection_reasons("sub", submission_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:reject_reason:"))
async def reject_submission(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    _, _, raw_id, reason_code = callback.data.split(":", 3)
    submission_id = int(raw_id)
    reason = REASONS.get(reason_code, REASONS["other"])
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        submission = await db.get(Submission, submission_id, with_for_update=True)
        if not submission or submission.status != SubmissionStatus.PENDING.value:
            await callback.answer("Xabar allaqachon ko‘rib chiqilgan.", show_alert=True)
            return
        submission.status = SubmissionStatus.REJECTED.value
        submission.rejection_reason = reason
        submission.reviewer_id = callback.from_user.id
        submission.reviewed_at = datetime.now(UTC)
        await audit(
            db,
            callback.from_user.id,
            "submission.rejected",
            "submission",
            submission.id,
            {"reason": reason_code},
        )
        await notify_user(
            bot,
            submission.user_id,
            f"❌ <b>#{submission.id}</b> xabaringiz rad etildi.\nSabab: {reason}",
        )
    await _remove_keyboard(callback)
    await callback.message.reply(f"❌ #{submission_id} rad etildi: {reason}")
    await callback.answer()


@router.callback_query(F.data.startswith("sub:reject_back:"))
async def submission_rejection_back(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    submission_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
        submission = await db.get(Submission, submission_id)
        if not submission or submission.status != SubmissionStatus.PENDING.value:
            await callback.answer("Xabar allaqachon ko‘rib chiqilgan.", show_alert=True)
            return
        username = await resolve_bot_username(bot, settings)
    await callback.message.edit_reply_markup(
        reply_markup=moderation_submission(submission.id, username, submission.token)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:ban:"))
async def choose_ban(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    submission_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
    await callback.message.edit_reply_markup(reply_markup=ban_confirmation(submission_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:ban_confirm:"))
async def ban_submission_author(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    submission_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        submission = await db.get(Submission, submission_id, with_for_update=True)
        if not submission:
            await callback.answer("Xabar topilmadi.", show_alert=True)
            return
        user = await db.get(User, submission.user_id)
        user.is_banned = True
        user.ban_reason = f"Submission #{submission.id}"
        if submission.status == SubmissionStatus.PENDING.value:
            submission.status = SubmissionStatus.REJECTED.value
            submission.rejection_reason = "Qoidabuzarlik sabab bloklandi"
            submission.reviewer_id = callback.from_user.id
            submission.reviewed_at = datetime.now(UTC)
        await audit(db, callback.from_user.id, "user.banned", "user", user.anon_code)
        await notify_user(bot, user.telegram_id, "🚫 Botdan foydalanishingiz cheklangan.")
    await _remove_keyboard(callback)
    await callback.message.reply(f"🚫 #{submission_id} muallifi bloklandi.")
    await callback.answer()


@router.callback_query(F.data.startswith("reply:approve:"))
async def approve_reply(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    reply_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        reply = await db.get(AnonymousReply, reply_id, with_for_update=True)
        if not reply or reply.status != SubmissionStatus.PENDING.value:
            await callback.answer("Javob allaqachon ko‘rib chiqilgan.", show_alert=True)
            return
        try:
            await publish_reply(db, bot, reply, callback.from_user.id)
        except (TelegramBadRequest, RuntimeError) as exc:
            await callback.answer(f"Kommentga yuborilmadi: {exc}", show_alert=True)
            return
    await _remove_keyboard(callback)
    await callback.message.reply(f"✅ Anonim komment #{reply_id} tasdiqlandi.")
    await callback.answer()


@router.callback_query(F.data.startswith("reply:reject:"))
async def choose_reply_rejection(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    reply_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
    await callback.message.edit_reply_markup(reply_markup=rejection_reasons("reply", reply_id))
    await callback.answer()


@router.callback_query(F.data.startswith("reply:reject_back:"))
async def reply_rejection_back(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    reply_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
    await callback.message.edit_reply_markup(reply_markup=moderation_reply(reply_id))
    await callback.answer()


@router.callback_query(F.data.startswith("reply:reject_reason:"))
async def reject_reply(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    _, _, raw_id, reason_code = callback.data.split(":", 3)
    reply_id = int(raw_id)
    reason = REASONS.get(reason_code, REASONS["other"])
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        reply = await db.get(AnonymousReply, reply_id, with_for_update=True)
        if not reply or reply.status != SubmissionStatus.PENDING.value:
            await callback.answer("Javob allaqachon ko‘rib chiqilgan.", show_alert=True)
            return
        reply.status = SubmissionStatus.REJECTED.value
        reply.rejection_reason = reason
        reply.reviewer_id = callback.from_user.id
        reply.reviewed_at = datetime.now(UTC)
        await audit(
            db,
            callback.from_user.id,
            "reply.rejected",
            "anonymous_reply",
            reply.id,
            {"reason": reason_code},
        )
        await notify_user(bot, reply.user_id, f"❌ Anonim javobingiz rad etildi.\nSabab: {reason}")
    await _remove_keyboard(callback)
    await callback.message.reply(f"❌ Anonim komment #{reply_id} rad etildi.")
    await callback.answer()


@router.callback_query(F.data.startswith("reply:ban:"))
async def ban_reply_author(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    reply_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        reply = await db.get(AnonymousReply, reply_id, with_for_update=True)
        if not reply:
            await callback.answer("Javob topilmadi.", show_alert=True)
            return
        user = await db.get(User, reply.user_id)
        user.is_banned = True
        user.ban_reason = f"Anonymous reply #{reply.id}"
        if reply.status == SubmissionStatus.PENDING.value:
            reply.status = SubmissionStatus.REJECTED.value
            reply.rejection_reason = "Qoidabuzarlik sabab bloklandi"
            reply.reviewer_id = callback.from_user.id
            reply.reviewed_at = datetime.now(UTC)
        await audit(db, callback.from_user.id, "user.banned", "user", user.anon_code)
        await notify_user(bot, user.telegram_id, "🚫 Botdan foydalanishingiz cheklangan.")
    await _remove_keyboard(callback)
    await callback.message.reply(f"🚫 Komment #{reply_id} muallifi bloklandi.")
    await callback.answer()
