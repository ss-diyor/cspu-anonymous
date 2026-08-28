from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.keyboards import (
    category_menu,
    comment_preview,
    confirm_data_deletion,
    confirm_filter_change,
    history_menu,
    inquiry_answer_button,
    main_menu,
    submission_preview,
)
from app.models import (
    Admin,
    AnonymousReply,
    Category,
    ContentFingerprint,
    Inquiry,
    InquiryStatus,
    Submission,
    SubmissionStatus,
)
from app.security import (
    content_fingerprint,
    inspect_content,
    make_token,
    parse_banned_words,
    user_is_banned,
)
from app.services.content import extract_content, send_content, validate_content
from app.services.publishing import (
    notify_user,
    publish_reply,
    publish_submission,
    resolve_bot_username,
    send_reply_to_moderation,
    send_submission_to_moderation,
)
from app.services.retention import erase_user_data
from app.services.store import (
    audit,
    clear_session,
    get_or_create_user,
    get_session,
    get_setting,
    is_admin,
    is_superadmin,
    set_session,
)

router = Router(name="user")

WELCOME = (
    "<b>Chirchiq davlat pedagogika universiteti anonim boti</b>\n\n"
    "Bu yerda kanalga anonim xabar yuborishingiz yoki postlarga anonim javob "
    "qoldirishingiz mumkin. Moderatorlar sizning ismingiz va username’ingizni ko‘rmaydi."
)

PRIVACY = (
    "<b>Qoidalar va maxfiylik</b>\n\n"
    "• Haqorat, tahdid, spam va noqonuniy material yubormang.\n"
    "• Boshqalarning telefon raqami, manzili yoki hujjatlarini ruxsatsiz joylamang.\n"
    "• Xabarlar kanalga bot nomidan yuboriladi; Telegram forward ishlatilmaydi.\n"
    "• Bot ishlashi va javobni sizga yetkazishi uchun Telegram ID texnik ravishda "
    "saqlanadi, ammo moderatorlarga ko‘rsatilmaydi.\n"
    "• Suiiste’mol holatida anonim identifikator vaqtincha yoki doimiy bloklanishi mumkin.\n"
    "• Rad etilgan kontent odatda 30 kun, muallif bog‘lanishi 90 kungacha saqlanadi.\n"
    "• Menyudan bazadagi ma’lumotlaringizni o‘chirishingiz mumkin; avval kanalga "
    "chiqqan xabarlar Telegram’dan avtomatik o‘chmaydi."
)


async def _access_or_warn(message: Message, db: AsyncSession):
    user = await get_or_create_user(db, message.from_user.id)
    if user_is_banned(user):
        await message.answer("🚫 Botdan foydalanishingiz cheklangan.")
        return None
    if user.is_banned and not user_is_banned(user):
        user.is_banned = False
        user.banned_until = None
        user.ban_reason = None
    return user


def _rate_limited(last_action_at: datetime | None, seconds: int) -> int:
    if not last_action_at:
        return 0
    if last_action_at.tzinfo is None:
        last_action_at = last_action_at.replace(tzinfo=UTC)
    remaining = seconds - int((datetime.now(UTC) - last_action_at).total_seconds())
    return max(0, remaining)


def _review_flags(text: str | None, banned_words: list[str], content_type: str) -> dict:
    result = inspect_content(text, banned_words)
    reasons = list(result.reasons)
    if content_type == "document":
        reasons.append("document")
    return {
        "reasons": list(dict.fromkeys(reasons)),
        "matched_words": list(result.matched_words),
    }


async def _route_deep_link(
    message: Message,
    payload: str,
    db: AsyncSession,
    bot: Bot,
    settings: Settings,
) -> bool:
    user_id = message.from_user.id
    if payload.startswith("comment_"):
        token = payload.removeprefix("comment_")
        submission = await db.scalar(
            select(Submission).where(
                Submission.comment_token == token,
                Submission.status == SubmissionStatus.PUBLISHED.value,
            )
        )
        if not submission or not submission.discussion_message_id:
            await message.answer("Bu post uchun anonim javob havolasi faol emas.")
            return True
        await set_session(
            db,
            user_id,
            "awaiting_comment",
            {"submission_id": submission.id},
            settings.session_ttl_minutes,
        )
        await message.answer(
            f"✍️ <b>#{submission.id}-postga anonim javob</b>\n\n"
            "Matn, rasm, video, PDF, ovozli xabar yoki animatsiya yuboring. "
            "Jarayon 30 daqiqa davomida faol."
        )
        return True

    if payload.startswith("answer_"):
        token = payload.removeprefix("answer_")
        inquiry = await db.scalar(
            select(Inquiry).where(
                Inquiry.token == token,
                Inquiry.status == InquiryStatus.OPEN.value,
            )
        )
        if not inquiry:
            await message.answer("Bu savol yopilgan yoki havola eskirgan.")
            return True
        submission = await db.get(Submission, inquiry.submission_id)
        if not submission or submission.user_id != user_id:
            await message.answer("Bu havola sizga tegishli emas.")
            return True
        await set_session(
            db,
            user_id,
            "awaiting_inquiry_answer",
            {"inquiry_id": inquiry.id},
            settings.session_ttl_minutes,
        )
        await message.answer(
            f"Moderator savoli:\n\n<b>{escape(inquiry.question)}</b>\n\nJavobingizni yozing."
        )
        return True

    if payload.startswith(("edit_", "ask_")):
        if not await is_admin(db, settings, user_id):
            await message.answer("Bu amal faqat moderatorlar uchun.")
            return True
        action, token = payload.split("_", 1)
        submission = await db.scalar(select(Submission).where(Submission.token == token))
        if not submission or submission.status != SubmissionStatus.PENDING.value:
            await message.answer("Xabar topilmadi yoki allaqachon ko‘rib chiqilgan.")
            return True
        if action == "ask" and submission.user_id is None:
            await message.answer("Muallif ma’lumoti o‘chirilgan; savol yuborib bo‘lmaydi.")
            return True
        state = "awaiting_admin_edit" if action == "edit" else "awaiting_admin_question"
        await set_session(
            db,
            user_id,
            state,
            {"submission_id": submission.id},
            settings.session_ttl_minutes,
        )
        prompt = (
            "Xabarning yangi matni yoki media izohini yuboring. Media fayl o‘zgarmaydi."
            if action == "edit"
            else "Anonim muallifga yuboriladigan savolni yozing."
        )
        await message.answer(prompt)
        return True
    return False


@router.message(CommandStart(), F.chat.type == "private")
async def start(
    message: Message,
    command: CommandObject,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        if not await _access_or_warn(message, db):
            return
        if command.args and await _route_deep_link(message, command.args, db, bot, settings):
            return
        await clear_session(db, message.from_user.id)
        await message.answer(WELCOME, reply_markup=main_menu())


@router.message(Command("cancel"), F.chat.type == "private")
async def cancel_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db, db.begin():
        await clear_session(db, message.from_user.id)
    await message.answer("Amal bekor qilindi.", reply_markup=main_menu())


@router.callback_query(F.data == "user:home")
async def home(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as db, db.begin():
        await clear_session(db, callback.from_user.id)
    await callback.message.edit_text(WELCOME, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "user:cancel")
async def cancel_callback(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as db, db.begin():
        await clear_session(db, callback.from_user.id)
    await callback.message.answer("Amal bekor qilindi.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "user:privacy")
async def privacy(callback: CallbackQuery) -> None:
    await callback.message.edit_text(PRIVACY, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "user:delete_data")
async def delete_data_prompt(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>Ma’lumotlarni o‘chirish</b>\n\n"
        "Bot bazasidagi Telegram ID, yuborilgan kontent va tarix muallifdan uziladi. "
        "Kanalda avval e’lon qilingan post va kommentlar Telegram kanalidan "
        "avtomatik o‘chmaydi. Davom etasizmi?",
        reply_markup=confirm_data_deletion(),
    )
    await callback.answer()


@router.callback_query(F.data == "user:delete_data_confirm")
async def delete_data_confirm(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        submission_message_ids = list(
            (
                await db.scalars(
                    select(Submission.moderation_message_id).where(
                        Submission.user_id == callback.from_user.id,
                        Submission.moderation_message_id.is_not(None),
                    )
                )
            ).all()
        )
        reply_message_ids = list(
            (
                await db.scalars(
                    select(AnonymousReply.moderation_message_id).where(
                        AnonymousReply.user_id == callback.from_user.id,
                        AnonymousReply.moderation_message_id.is_not(None),
                    )
                )
            ).all()
        )
        counts = await erase_user_data(db, callback.from_user.id)
        await audit(
            db,
            None,
            "user.data_erased",
            "anonymous_user",
            None,
            counts,
        )
    for message_id in submission_message_ids + reply_message_ids:
        try:
            await bot.delete_message(settings.moderation_chat_id, message_id)
        except TelegramBadRequest:
            continue
    await callback.message.edit_text(
        "✅ Bot bazasidagi shaxsiy bog‘lanishlar va saqlangan kontent o‘chirildi. "
        "Botdan yana foydalansangiz yangi anonim profil yaratiladi.",
        reply_markup=main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "user:new")
async def new_submission(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        user = await get_or_create_user(db, callback.from_user.id)
        if user_is_banned(user):
            await callback.answer("Botdan foydalanishingiz cheklangan.", show_alert=True)
            return
        categories = list(
            (
                await db.scalars(
                    select(Category).where(Category.enabled.is_(True)).order_by(Category.sort_order)
                )
            ).all()
        )
        await clear_session(db, callback.from_user.id)
    await callback.message.edit_text(
        "Xabaringiz kategoriyasini tanlang:", reply_markup=category_menu(categories)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("category:"))
async def select_category(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Noto‘g‘ri kategoriya.", show_alert=True)
        return
    async with session_factory() as db, db.begin():
        category = await db.get(Category, category_id)
        if not category or not category.enabled:
            await callback.answer("Bu kategoriya hozir faol emas.", show_alert=True)
            return
        await set_session(
            db,
            callback.from_user.id,
            "awaiting_submission",
            {"category_id": category.id},
            settings.session_ttl_minutes,
        )
    await callback.message.edit_text(
        f"{category.emoji} <b>{category.title}</b>\n\n"
        "Xabaringizni yuboring. Matn, rasm, video, PDF, ovozli xabar yoki "
        "animatsiya qabul qilinadi.\n\nBekor qilish: /cancel"
    )
    await callback.answer()


@router.callback_query(F.data.in_({"draft:rewrite", "comment:rewrite"}))
async def rewrite(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        current = await get_session(db, callback.from_user.id)
        if not current:
            await callback.answer("Jarayon muddati tugagan.", show_alert=True)
            return
        if callback.data == "draft:rewrite":
            category_id = current.payload.get("category_id")
            await set_session(
                db,
                callback.from_user.id,
                "awaiting_submission",
                {"category_id": category_id},
                settings.session_ttl_minutes,
            )
        else:
            submission_id = current.payload.get("submission_id")
            await set_session(
                db,
                callback.from_user.id,
                "awaiting_comment",
                {"submission_id": submission_id},
                settings.session_ttl_minutes,
            )
    await callback.message.answer("Yangi variantni yuboring.")
    await callback.answer()


@router.callback_query(F.data == "draft:submit")
async def submit_draft(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        current = await get_session(db, callback.from_user.id, lock=True)
        if not current or current.state != "preview_submission":
            await callback.answer("Xabar muddati tugagan. Qaytadan boshlang.", show_alert=True)
            return
        user = await get_or_create_user(db, callback.from_user.id)
        if user_is_banned(user):
            await callback.answer("Botdan foydalanishingiz cheklangan.", show_alert=True)
            return
        remaining = _rate_limited(user.last_action_at, settings.rate_limit_seconds)
        if remaining:
            await callback.answer(f"Yana {remaining} soniya kuting.", show_alert=True)
            return
        payload = current.payload
        fingerprint = content_fingerprint(
            payload["content_type"], payload.get("text"), payload.get("file_unique_id")
        )
        await db.execute(
            delete(ContentFingerprint).where(
                ContentFingerprint.created_at < datetime.now(UTC) - timedelta(days=7)
            )
        )
        duplicate = await db.scalar(
            select(ContentFingerprint.id).where(
                ContentFingerprint.user_id == user.telegram_id,
                ContentFingerprint.fingerprint == fingerprint,
                ContentFingerprint.created_at >= datetime.now(UTC) - timedelta(hours=24),
            )
        )
        if duplicate:
            await callback.answer("Bu xabar avval yuborilgan.", show_alert=True)
            return
        submission = Submission(
            token=make_token(),
            comment_token=make_token(),
            user_id=user.telegram_id,
            category_id=int(payload["category_id"]),
            content_type=payload["content_type"],
            text=payload.get("text"),
            file_id=payload.get("file_id"),
            file_unique_id=payload.get("file_unique_id"),
            status=SubmissionStatus.PENDING.value,
        )
        db.add(submission)
        db.add(
            ContentFingerprint(
                user_id=user.telegram_id,
                fingerprint=fingerprint,
            )
        )
        user.last_action_at = datetime.now(UTC)
        await db.flush()
        mode = await get_setting(db, "post_moderation_mode", "manual")
        banned_words = parse_banned_words(await get_setting(db, "banned_words", ""))
        submission.review_flags = _review_flags(
            submission.text, banned_words, submission.content_type
        )
        should_review = (
            mode == "manual"
            or bool(submission.review_flags["reasons"] or submission.review_flags["matched_words"])
            or (mode == "hybrid" and submission.content_type != "text")
        )
        if should_review:
            await send_submission_to_moderation(db, bot, settings, submission)
            result_text = (
                f"⏳ <b>#{submission.id}</b> xabaringiz moderatorlarga yuborildi. "
                "Holatini “Xabarlarim” bo‘limidan tekshirishingiz mumkin."
            )
        else:
            await publish_submission(db, bot, settings, submission, send_notification=False)
            result_text = f"✅ <b>#{submission.id}</b> xabaringiz kanalga joylandi."
        await clear_session(db, callback.from_user.id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.message.answer(result_text, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "comment:submit")
async def submit_comment(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        current = await get_session(db, callback.from_user.id, lock=True)
        if not current or current.state != "preview_comment":
            await callback.answer("Javob muddati tugagan.", show_alert=True)
            return
        user = await get_or_create_user(db, callback.from_user.id)
        if user_is_banned(user):
            await callback.answer("Botdan foydalanishingiz cheklangan.", show_alert=True)
            return
        remaining = _rate_limited(user.last_action_at, settings.rate_limit_seconds)
        if remaining:
            await callback.answer(f"Yana {remaining} soniya kuting.", show_alert=True)
            return
        payload = current.payload
        submission = await db.get(Submission, int(payload["submission_id"]))
        if not submission or not submission.discussion_message_id:
            await callback.answer("Post kommentlari mavjud emas.", show_alert=True)
            return
        fingerprint = content_fingerprint(
            f"comment:{submission.id}:{payload['content_type']}",
            payload.get("text"),
            payload.get("file_unique_id"),
        )
        duplicate = await db.scalar(
            select(ContentFingerprint.id).where(
                ContentFingerprint.user_id == user.telegram_id,
                ContentFingerprint.fingerprint == fingerprint,
                ContentFingerprint.created_at >= datetime.now(UTC) - timedelta(hours=24),
            )
        )
        if duplicate:
            await callback.answer("Bu javob avval yuborilgan.", show_alert=True)
            return
        reply = AnonymousReply(
            token=make_token(),
            submission_id=submission.id,
            user_id=user.telegram_id,
            content_type=payload["content_type"],
            text=payload.get("text"),
            file_id=payload.get("file_id"),
            file_unique_id=payload.get("file_unique_id"),
            status=SubmissionStatus.PENDING.value,
        )
        db.add(reply)
        db.add(
            ContentFingerprint(
                user_id=user.telegram_id,
                fingerprint=fingerprint,
            )
        )
        user.last_action_at = datetime.now(UTC)
        await db.flush()
        mode = await get_setting(db, "reply_moderation_mode", "manual")
        banned_words = parse_banned_words(await get_setting(db, "banned_words", ""))
        reply.review_flags = _review_flags(reply.text, banned_words, reply.content_type)
        should_review = (
            mode == "manual"
            or bool(reply.review_flags["reasons"] or reply.review_flags["matched_words"])
            or (mode == "hybrid" and reply.content_type != "text")
        )
        if should_review:
            await send_reply_to_moderation(db, bot, settings, reply)
            result = "⏳ Anonim javobingiz moderatsiyaga yuborildi."
        else:
            await publish_reply(db, bot, reply, send_notification=False)
            result = "✅ Anonim javobingiz post kommentiga joylandi."
        await clear_session(db, callback.from_user.id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.message.answer(result, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "user:history")
async def history(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        submissions = list(
            (
                await db.scalars(
                    select(Submission)
                    .where(Submission.user_id == callback.from_user.id)
                    .order_by(Submission.created_at.desc())
                    .limit(10)
                )
            ).all()
        )
    labels = {
        SubmissionStatus.PENDING.value: "⏳ Kutilmoqda",
        SubmissionStatus.PUBLISHED.value: "✅ E’lon qilindi",
        SubmissionStatus.REJECTED.value: "❌ Rad etildi",
        SubmissionStatus.WITHDRAWN.value: "↩️ Bekor qilindi",
    }
    if not submissions:
        text = "Siz hali anonim xabar yubormagansiz."
    else:
        lines = ["<b>Oxirgi xabarlaringiz</b>", ""]
        for item in submissions:
            line = f"#{item.id} — {labels.get(item.status, item.status)}"
            if item.rejection_reason:
                line += f" ({item.rejection_reason})"
            lines.append(line)
        text = "\n".join(lines)
    pending_ids = [item.id for item in submissions if item.status == SubmissionStatus.PENDING.value]
    await callback.message.edit_text(text, reply_markup=history_menu(pending_ids))
    await callback.answer()


@router.callback_query(F.data.startswith("user:withdraw:"))
async def withdraw_submission(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    submission_id = int(callback.data.rsplit(":", 1)[1])
    moderation_message_id: int | None = None
    async with session_factory() as db, db.begin():
        submission = await db.get(Submission, submission_id, with_for_update=True)
        if (
            not submission
            or submission.user_id != callback.from_user.id
            or submission.status != SubmissionStatus.PENDING.value
        ):
            await callback.answer("Bu xabarni bekor qilib bo‘lmaydi.", show_alert=True)
            return
        submission.status = SubmissionStatus.WITHDRAWN.value
        submission.rejection_reason = "Muallif bekor qildi"
        submission.reviewed_at = datetime.now(UTC)
        moderation_message_id = submission.moderation_message_id
        await audit(db, None, "submission.withdrawn", "submission", submission.id)
    if moderation_message_id:
        try:
            await bot.edit_message_reply_markup(
                settings.moderation_chat_id,
                moderation_message_id,
                reply_markup=None,
            )
            await bot.send_message(
                settings.moderation_chat_id,
                f"↩️ #{submission_id} xabarini muallif bekor qildi.",
            )
        except TelegramBadRequest:
            pass
    await callback.message.edit_text("Xabar bekor qilindi.", reply_markup=main_menu())
    await callback.answer()


@router.message(F.chat.type == "private")
async def private_input(
    message: Message,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        if not await _access_or_warn(message, db):
            return
        current = await get_session(db, message.from_user.id)
        if not current:
            await message.answer("Kerakli amalni menyudan tanlang.", reply_markup=main_menu())
            return

        if current.state in {"awaiting_submission", "awaiting_comment"}:
            content = extract_content(message)
            if not content:
                await message.answer(
                    "Bu turdagi xabar qo‘llab-quvvatlanmaydi. Matn yoki media yuboring."
                )
                return
            error = validate_content(content)
            if error:
                await message.answer(error)
                return
            payload = dict(current.payload)
            payload.update(content)
            is_submission = current.state == "awaiting_submission"
            try:
                preview_message = await send_content(
                    bot,
                    message.chat.id,
                    content_type=content["content_type"],
                    text=content.get("text"),
                    file_id=content.get("file_id"),
                    prefix="<b>Oldindan ko‘rish</b>",
                    reply_markup=submission_preview() if is_submission else comment_preview(),
                )
            except ValueError as exc:
                await message.answer(str(exc))
                return
            if content["content_type"] == "document" and preview_message.document:
                payload["file_id"] = preview_message.document.file_id
                payload["file_unique_id"] = preview_message.document.file_unique_id
                payload["file_name"] = "anonim_hujjat.pdf"
            await set_session(
                db,
                message.from_user.id,
                "preview_submission" if is_submission else "preview_comment",
                payload,
                settings.session_ttl_minutes,
            )
            return

        if current.state == "awaiting_admin_edit":
            if not await is_admin(db, settings, message.from_user.id):
                await clear_session(db, message.from_user.id)
                return
            submission = await db.get(Submission, int(current.payload["submission_id"]))
            if not submission or submission.status != SubmissionStatus.PENDING.value:
                await clear_session(db, message.from_user.id)
                await message.answer("Xabar allaqachon ko‘rib chiqilgan.")
                return
            if not message.text:
                await message.answer("Faqat yangi matn yoki media izohini yuboring.")
                return
            limit = 3800 if submission.content_type == "text" else 850
            if len(message.text) > limit:
                await message.answer(f"Matn {limit} belgidan oshmasligi kerak.")
                return
            if submission.moderation_message_id:
                try:
                    await bot.edit_message_reply_markup(
                        settings.moderation_chat_id,
                        submission.moderation_message_id,
                        reply_markup=None,
                    )
                except TelegramBadRequest:
                    pass
            submission.text = message.text
            banned_words = parse_banned_words(await get_setting(db, "banned_words", ""))
            submission.review_flags = _review_flags(
                submission.text, banned_words, submission.content_type
            )
            await send_submission_to_moderation(db, bot, settings, submission)
            await audit(
                db,
                message.from_user.id,
                "submission.edited",
                "submission",
                submission.id,
            )
            await clear_session(db, message.from_user.id)
            await message.answer(
                f"✅ #{submission.id} xabari yangilandi va moderatsiyaga qaytarildi."
            )
            return

        if current.state == "awaiting_admin_question":
            if not await is_admin(db, settings, message.from_user.id) or not message.text:
                await message.answer("Savolni matn ko‘rinishida yuboring.")
                return
            if len(message.text) > 3000:
                await message.answer("Savol 3000 belgidan oshmasligi kerak.")
                return
            submission = await db.get(Submission, int(current.payload["submission_id"]))
            if not submission:
                await clear_session(db, message.from_user.id)
                await message.answer("Xabar topilmadi.")
                return
            inquiry = Inquiry(
                token=make_token(),
                submission_id=submission.id,
                admin_id=message.from_user.id,
                question=message.text,
                status=InquiryStatus.OPEN.value,
            )
            db.add(inquiry)
            await db.flush()
            username = await resolve_bot_username(bot, settings)
            await notify_user(
                bot,
                submission.user_id,
                f"💬 <b>#{submission.id} xabaringiz bo‘yicha moderator savoli:</b>\n\n"
                f"{escape(message.text)}",
                reply_markup=inquiry_answer_button(username, inquiry.token),
            )
            await audit(db, message.from_user.id, "inquiry.sent", "inquiry", inquiry.id)
            await clear_session(db, message.from_user.id)
            await message.answer("✅ Savol anonim muallifga yuborildi.")
            return

        if current.state == "awaiting_inquiry_answer":
            if not message.text:
                await message.answer("Javobni matn ko‘rinishida yuboring.")
                return
            if len(message.text) > 3500:
                await message.answer("Javob 3500 belgidan oshmasligi kerak.")
                return
            inquiry = await db.get(Inquiry, int(current.payload["inquiry_id"]))
            if not inquiry or inquiry.status != InquiryStatus.OPEN.value:
                await clear_session(db, message.from_user.id)
                await message.answer("Bu savol yopilgan.")
                return
            submission = await db.get(Submission, inquiry.submission_id)
            if not submission or submission.user_id != message.from_user.id:
                await clear_session(db, message.from_user.id)
                return
            inquiry.answer = message.text
            inquiry.status = InquiryStatus.ANSWERED.value
            inquiry.answered_at = datetime.now(UTC)
            await bot.send_message(
                settings.moderation_chat_id,
                f"💬 <b>#{submission.id} muallifidan anonim javob</b>\n\n{escape(message.text)}",
            )
            await audit(db, message.from_user.id, "inquiry.answered", "inquiry", inquiry.id)
            await clear_session(db, message.from_user.id)
            await message.answer("✅ Javobingiz moderatorga anonim tarzda yuborildi.")
            return

        if current.state == "awaiting_admin_add":
            if not await is_superadmin(db, settings, message.from_user.id):
                await clear_session(db, message.from_user.id)
                return
            parts = message.text.split() if message.text else []
            if not parts or not parts[0].lstrip("-").isdigit():
                await message.answer(
                    "Telegram ID va rolni yuboring: <code>123456 moderator</code> yoki "
                    "<code>123456 senior_moderator</code>."
                )
                return
            admin_id = int(parts[0])
            role = parts[1] if len(parts) > 1 else "moderator"
            if role not in {"moderator", "senior_moderator"}:
                await message.answer("Rol moderator yoki senior_moderator bo‘lishi kerak.")
                return
            existing = await db.get(Admin, admin_id)
            if existing:
                await message.answer("Bu foydalanuvchi allaqachon moderator.")
                return
            db.add(Admin(telegram_id=admin_id, role=role, added_by=message.from_user.id))
            await audit(
                db,
                message.from_user.id,
                "admin.added",
                "admin",
                admin_id,
                {"role": role},
            )
            await clear_session(db, message.from_user.id)
            await message.answer(f"✅ {admin_id} {role} sifatida qo‘shildi.")
            return

        if current.state == "awaiting_banned_words":
            if not await is_superadmin(db, settings, message.from_user.id) or not message.text:
                await message.answer("Ro‘yxatni matn ko‘rinishida yuboring.")
                return
            words = [] if message.text.strip() == "-" else parse_banned_words(message.text)
            value = ", ".join(words)
            if len(value) > 2000:
                await message.answer("Ro‘yxat 2000 belgidan oshmasligi kerak.")
                return
            await set_session(
                db,
                message.from_user.id,
                "confirm_banned_words",
                {"value": value},
                settings.session_ttl_minutes,
            )
            shown = escape(value) if value else "ro‘yxatni tozalash"
            await message.answer(
                f"Quyidagi filtr o‘zgarishini tasdiqlaysizmi?\n\n{shown}",
                reply_markup=confirm_filter_change(),
            )
            return

        await message.answer("Jarayon holati noma’lum. /cancel buyrug‘i bilan bekor qiling.")
