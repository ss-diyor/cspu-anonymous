from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.keyboards import (
    admin_menu,
    categories_admin_menu,
    confirm_category_change,
    confirm_mode_change,
    confirm_remove_moderator,
    moderators_menu,
    modes_menu,
)
from app.models import (
    Admin,
    AnonymousReply,
    AuditLog,
    Category,
    Submission,
    SubmissionStatus,
    User,
)
from app.services.store import (
    audit,
    clear_session,
    get_session,
    get_setting,
    has_admin_role,
    is_admin,
    is_superadmin,
    set_session,
    set_setting,
)

router = Router(name="admin")


async def _authorized(
    callback: CallbackQuery,
    db: AsyncSession,
    settings: Settings,
) -> bool:
    if await is_admin(db, settings, callback.from_user.id):
        return True
    await callback.answer("Bu amal faqat administratorlar uchun.", show_alert=True)
    return False


async def _superadmin_authorized(
    callback: CallbackQuery,
    db: AsyncSession,
    settings: Settings,
) -> bool:
    if await is_superadmin(db, settings, callback.from_user.id):
        return True
    await callback.answer("Bu sozlama faqat superadmin uchun.", show_alert=True)
    return False


async def _senior_authorized(
    callback: CallbackQuery,
    db: AsyncSession,
    settings: Settings,
) -> bool:
    if await has_admin_role(db, settings, callback.from_user.id, "senior_moderator"):
        return True
    await callback.answer("Bu amal senior moderator yoki superadmin uchun.", show_alert=True)
    return False


@router.message(Command("admin"), F.chat.type == "private")
async def admin_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        allowed = await is_admin(db, settings, message.from_user.id)
    if not allowed:
        await message.answer("Sizda admin panelga kirish huquqi yo‘q.")
        return
    await message.answer("<b>Admin panel</b>", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:home")
async def admin_home(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
    await callback.message.edit_text("<b>Admin panel</b>", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def stats(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
        total_users = await db.scalar(select(func.count()).select_from(User)) or 0
        total_submissions = await db.scalar(select(func.count()).select_from(Submission)) or 0
        pending = (
            await db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.status == SubmissionStatus.PENDING.value)
            )
            or 0
        )
        published = (
            await db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.status == SubmissionStatus.PUBLISHED.value)
            )
            or 0
        )
        rejected = (
            await db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.status == SubmissionStatus.REJECTED.value)
            )
            or 0
        )
        total_replies = await db.scalar(select(func.count()).select_from(AnonymousReply)) or 0
        banned = (
            await db.scalar(select(func.count()).select_from(User).where(User.is_banned.is_(True)))
            or 0
        )
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today = (
            await db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.created_at >= today_start)
            )
            or 0
        )
        category_rows = (
            await db.execute(
                select(Category.emoji, Category.title, func.count(Submission.id))
                .join(Submission, Submission.category_id == Category.id)
                .group_by(Category.id, Category.emoji, Category.title)
                .order_by(func.count(Submission.id).desc())
                .limit(5)
            )
        ).all()
        moderator_rows = (
            await db.execute(
                select(AuditLog.actor_id, func.count(AuditLog.id))
                .where(
                    AuditLog.actor_id.is_not(None),
                    AuditLog.action.in_(("submission.published", "submission.rejected")),
                )
                .group_by(AuditLog.actor_id)
                .order_by(func.count(AuditLog.id).desc())
                .limit(5)
            )
        ).all()
        reviewed_rows = (
            await db.execute(
                select(Submission.created_at, Submission.reviewed_at)
                .where(Submission.reviewed_at.is_not(None))
                .order_by(Submission.reviewed_at.desc())
                .limit(1000)
            )
        ).all()
        durations = [
            (reviewed_at - created_at).total_seconds()
            for created_at, reviewed_at in reviewed_rows
            if reviewed_at and created_at
        ]
        average_minutes = sum(durations) / len(durations) / 60 if durations else 0
    text = (
        "<b>📊 Statistika</b>\n\n"
        f"Foydalanuvchilar: <b>{total_users}</b>\n"
        f"Jami xabarlar: <b>{total_submissions}</b>\n"
        f"Bugun kelgan: <b>{today}</b>\n"
        f"• Kutilmoqda: {pending}\n"
        f"• E’lon qilindi: {published}\n"
        f"• Rad etildi: {rejected}\n"
        f"Anonim kommentlar: <b>{total_replies}</b>\n"
        f"Bloklanganlar: <b>{banned}</b>\n"
        f"O‘rtacha ko‘rib chiqish: <b>{average_minutes:.1f} daqiqa</b>"
    )
    if category_rows:
        text += "\n\n<b>Faol kategoriyalar</b>\n" + "\n".join(
            f"{emoji} {escape(title)}: {count}" for emoji, title, count in category_rows
        )
    if moderator_rows:
        text += "\n\n<b>Moderatorlar faoliyati</b>\n" + "\n".join(
            f"<code>{actor_id}</code>: {count}" for actor_id, count in moderator_rows
        )
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:modes")
async def modes(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _superadmin_authorized(callback, db, settings):
            return
        post_mode = await get_setting(db, "post_moderation_mode", "manual")
        reply_mode = await get_setting(db, "reply_moderation_mode", "manual")
    await callback.message.edit_text(
        "<b>Moderatsiya rejimlari</b>\n\n"
        "Moderator — har bir xabar tekshiriladi.\n"
        "Avtomatik — xavfsiz xabar darhol chiqadi; filtrlangan xabar tekshiriladi.\n"
        "Gibrid — media, havola yoki filtrlangan matn tekshiriladi.",
        reply_markup=modes_menu(post_mode, reply_mode),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:cycle_mode:"))
async def cycle_mode(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    target = callback.data.rsplit(":", 1)[1]
    choices = ("manual", "auto", "hybrid")
    key = "post_moderation_mode" if target == "post" else "reply_moderation_mode"
    async with session_factory() as db:
        if not await _superadmin_authorized(callback, db, settings):
            return
        current = await get_setting(db, key, "manual")
        value = (
            choices[(choices.index(current) + 1) % len(choices)] if current in choices else "manual"
        )
    labels = {"manual": "Moderator", "auto": "Avtomatik", "hybrid": "Gibrid"}
    await callback.message.edit_text(
        f"<b>Muhim sozlama</b>\n\n{target} rejimini "
        f"<b>{labels[value]}</b> holatiga o‘zgartirishni tasdiqlaysizmi?",
        reply_markup=confirm_mode_change(target, value),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:confirm_mode:"))
async def confirm_moderation_mode(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    _, _, target, value = callback.data.split(":", 3)
    if target not in {"post", "reply"} or value not in {"manual", "auto", "hybrid"}:
        await callback.answer("Noto‘g‘ri sozlama.", show_alert=True)
        return
    key = "post_moderation_mode" if target == "post" else "reply_moderation_mode"
    async with session_factory() as db, db.begin():
        if not await _superadmin_authorized(callback, db, settings):
            return
        await set_setting(db, key, value, callback.from_user.id)
        post_mode = await get_setting(db, "post_moderation_mode", "manual")
        reply_mode = await get_setting(db, "reply_moderation_mode", "manual")
    for admin_id in settings.superadmin_ids:
        if admin_id == callback.from_user.id:
            continue
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ Moderatsiya sozlamasi o‘zgardi: {target} = {value}. "
                f"Amalni bajargan: <code>{callback.from_user.id}</code>",
            )
        except Exception:
            continue
    await callback.message.edit_text(
        "Rejim o‘zgartirildi.", reply_markup=modes_menu(post_mode, reply_mode)
    )
    await callback.answer("Tasdiqlandi")


@router.callback_query(F.data == "admin:categories")
async def categories(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _superadmin_authorized(callback, db, settings):
            return
        items = list((await db.scalars(select(Category).order_by(Category.sort_order))).all())
    await callback.message.edit_text(
        "<b>Kategoriyalar</b>\nKategoriya ustiga bosib yoqing yoki o‘chiring.",
        reply_markup=categories_admin_menu(items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:toggle_category:"))
async def toggle_category(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    category_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db:
        if not await _superadmin_authorized(callback, db, settings):
            return
        category = await db.get(Category, category_id)
        if not category:
            await callback.answer("Kategoriya topilmadi.", show_alert=True)
            return
        title = category.title
        action = "o‘chirish" if category.enabled else "yoqish"
    await callback.message.edit_text(
        f"<b>Muhim sozlama</b>\n\n{escape(title)} kategoriyasini {action}ni tasdiqlaysizmi?",
        reply_markup=confirm_category_change(category_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:confirm_category:"))
async def confirm_category_toggle(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    category_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db, db.begin():
        if not await _superadmin_authorized(callback, db, settings):
            return
        category = await db.get(Category, category_id, with_for_update=True)
        if not category:
            await callback.answer("Kategoriya topilmadi.", show_alert=True)
            return
        category.enabled = not category.enabled
        await audit(
            db,
            callback.from_user.id,
            "category.toggled",
            "category",
            category.id,
            {"enabled": category.enabled},
        )
        items = list((await db.scalars(select(Category).order_by(Category.sort_order))).all())
    await callback.message.edit_text(
        "<b>Kategoriyalar</b>\nKategoriya ustiga bosib yoqing yoki o‘chiring.",
        reply_markup=categories_admin_menu(items),
    )
    await callback.answer("O‘zgartirildi")


@router.callback_query(F.data == "admin:moderators")
async def moderators(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
        admins = list((await db.scalars(select(Admin).order_by(Admin.created_at))).all())
        can_manage = await is_superadmin(db, settings, callback.from_user.id)
    lines = ["<b>Moderatorlar</b>", ""]
    lines.extend(f"• <code>{item.telegram_id}</code> — {item.role}" for item in admins)
    if not can_manage:
        lines.append("\nFaqat superadmin moderatorlarni o‘zgartira oladi.")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=moderators_menu(
            [item.telegram_id for item in admins if item.role != "superadmin"], can_manage
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:add_moderator")
async def add_moderator_prompt(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        if not await is_superadmin(db, settings, callback.from_user.id):
            await callback.answer("Faqat superadmin uchun.", show_alert=True)
            return
        await set_session(
            db,
            callback.from_user.id,
            "awaiting_admin_add",
            {},
            settings.session_ttl_minutes,
        )
    await callback.message.answer(
        "Telegram ID va rolni yuboring. Masalan:\n"
        "<code>123456789 moderator</code> yoki "
        "<code>123456789 senior_moderator</code>.\n\n"
        "U avval botga /start yuborgan bo‘lishi kerak."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:remove_moderator:"))
async def remove_moderator_prompt(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    admin_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db:
        if not await is_superadmin(db, settings, callback.from_user.id):
            await callback.answer("Faqat superadmin uchun.", show_alert=True)
            return
    await callback.message.edit_text(
        f"<code>{admin_id}</code> moderatorini olib tashlaysizmi?",
        reply_markup=confirm_remove_moderator(admin_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:remove_confirm:"))
async def remove_moderator(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    admin_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as db, db.begin():
        if not await is_superadmin(db, settings, callback.from_user.id):
            await callback.answer("Faqat superadmin uchun.", show_alert=True)
            return
        admin = await db.get(Admin, admin_id)
        if not admin or admin.role == "superadmin":
            await callback.answer(
                "Moderator topilmadi yoki olib tashlab bo‘lmaydi.", show_alert=True
            )
            return
        await db.delete(admin)
        await audit(db, callback.from_user.id, "admin.removed", "admin", admin_id)
    await callback.message.edit_text("Moderator olib tashlandi.", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:filters")
async def filters(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        if not await _superadmin_authorized(callback, db, settings):
            return
        words = await get_setting(db, "banned_words", "")
        await set_session(
            db,
            callback.from_user.id,
            "awaiting_banned_words",
            {},
            settings.session_ttl_minutes,
        )
    shown = escape(words) if words else "<i>Ro‘yxat bo‘sh</i>"
    await callback.message.answer(
        "<b>Taqiqlangan so‘zlar</b>\n\n"
        f"Hozir: {shown}\n\n"
        "Yangi ro‘yxatni vergul bilan ajratib yuboring. Tozalash uchun <code>-</code> yuboring."
    )
    await callback.answer()


@router.callback_query(F.data == "admin:confirm_filters")
async def confirm_filters(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        if not await _superadmin_authorized(callback, db, settings):
            return
        current = await get_session(db, callback.from_user.id, lock=True)
        if not current or current.state != "confirm_banned_words":
            await callback.answer("Tasdiqlash muddati tugagan.", show_alert=True)
            return
        value = str(current.payload.get("value", ""))
        await set_setting(db, "banned_words", value, callback.from_user.id)
        await clear_session(db, callback.from_user.id)
    for admin_id in settings.superadmin_ids:
        if admin_id == callback.from_user.id:
            continue
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ So‘z filtri yangilandi. Amalni bajargan: <code>{callback.from_user.id}</code>",
            )
        except Exception:
            continue
    await callback.message.edit_text("✅ So‘z filtri yangilandi.", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:cancel_setting")
async def cancel_setting(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db, db.begin():
        if not await _superadmin_authorized(callback, db, settings):
            return
        await clear_session(db, callback.from_user.id)
    await callback.message.edit_text("O‘zgarish bekor qilindi.", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:blocked")
async def blocked_users(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _senior_authorized(callback, db, settings):
            return
        users = list(
            (
                await db.scalars(
                    select(User)
                    .where(User.is_banned.is_(True))
                    .order_by(User.created_at.desc())
                    .limit(20)
                )
            ).all()
        )
    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(
            text=f"Blokdan chiqarish: {user.anon_code}",
            callback_data=f"admin:unban:{user.anon_code}",
        )
    builder.button(text="⬅️ Admin panel", callback_data="admin:home")
    builder.adjust(1)
    lines = ["<b>Bloklangan anonim foydalanuvchilar</b>", ""]
    lines.extend(
        f"• <code>{user.anon_code}</code> — {escape(user.ban_reason or 'Sababsiz')}"
        for user in users
    )
    if not users:
        lines.append("Ro‘yxat bo‘sh.")
    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:unban:"))
async def unban_user(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    anon_code = callback.data.rsplit(":", 1)[1]
    async with session_factory() as db, db.begin():
        if not await _senior_authorized(callback, db, settings):
            return
        user = await db.scalar(select(User).where(User.anon_code == anon_code))
        if not user:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return
        code = user.anon_code
        user.is_banned = False
        user.banned_until = None
        user.ban_reason = None
        user.violation_count = 0
        await audit(db, callback.from_user.id, "user.unbanned", "user", code)
    await callback.answer(f"{code} blokdan chiqarildi", show_alert=True)
    await callback.message.edit_text("Foydalanuvchi blokdan chiqarildi.", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:channel")
async def channel_status(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
            return
    webhook = escape(settings.webhook_url or "Polling/lokal rejim")
    text = (
        "<b>Kanal va deploy holati</b>\n\n"
        f"Kanal ID: <code>{settings.channel_id}</code>\n"
        f"Discussion ID: <code>{settings.discussion_chat_id}</code>\n"
        f"Moderatsiya ID: <code>{settings.moderation_chat_id}</code>\n"
        f"Webhook: <code>{webhook}</code>\n\n"
        "Chat ID lar xavfsizlik sabab Railway environment variables orqali o‘zgartiriladi."
    )
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:audit")
async def audit_log(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await is_superadmin(db, settings, callback.from_user.id):
            await callback.answer("Audit jurnali faqat superadmin uchun.", show_alert=True)
            return
        rows = list(
            (
                await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20))
            ).all()
        )
    lines = ["<b>Oxirgi 20 ta audit hodisasi</b>", ""]
    for item in rows:
        actor = str(item.actor_id) if item.actor_id else "system"
        target = f" {item.target_type}:{item.target_id}" if item.target_type else ""
        lines.append(
            f"<code>{item.created_at:%m-%d %H:%M}</code> · "
            f"{escape(item.action)} · <code>{actor}</code>{escape(target)}"
        )
    if not rows:
        lines.append("Jurnal hozircha bo‘sh.")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()
