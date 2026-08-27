from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.keyboards import (
    admin_menu,
    categories_admin_menu,
    confirm_remove_moderator,
    moderators_menu,
    modes_menu,
)
from app.models import Admin, AnonymousReply, Category, Submission, SubmissionStatus, User
from app.services.store import (
    audit,
    get_setting,
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
    text = (
        "<b>📊 Statistika</b>\n\n"
        f"Foydalanuvchilar: <b>{total_users}</b>\n"
        f"Jami xabarlar: <b>{total_submissions}</b>\n"
        f"• Kutilmoqda: {pending}\n"
        f"• E’lon qilindi: {published}\n"
        f"• Rad etildi: {rejected}\n"
        f"Anonim kommentlar: <b>{total_replies}</b>\n"
        f"Bloklanganlar: <b>{banned}</b>"
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
        if not await _authorized(callback, db, settings):
            return
        post_mode = await get_setting(db, "post_moderation_mode", "manual")
        reply_mode = await get_setting(db, "reply_moderation_mode", "manual")
    await callback.message.edit_text(
        "<b>Moderatsiya rejimlari</b>\n\n"
        "Moderator — har bir xabar tekshiriladi.\n"
        "Avtomatik — xabar darhol chiqadi.\n"
        "Gibrid — havola yoki taqiqlangan so‘z bo‘lsa tekshiriladi.",
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
    key = "post_moderation_mode" if target == "post" else "reply_moderation_mode"
    choices = ("manual", "auto", "hybrid")
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        current = await get_setting(db, key, "manual")
        value = (
            choices[(choices.index(current) + 1) % len(choices)] if current in choices else "manual"
        )
        await set_setting(db, key, value, callback.from_user.id)
        post_mode = await get_setting(db, "post_moderation_mode", "manual")
        reply_mode = await get_setting(db, "reply_moderation_mode", "manual")
    await callback.message.edit_reply_markup(reply_markup=modes_menu(post_mode, reply_mode))
    await callback.answer("Rejim o‘zgartirildi")


@router.callback_query(F.data == "admin:categories")
async def categories(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
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
    async with session_factory() as db, db.begin():
        if not await _authorized(callback, db, settings):
            return
        category = await db.get(Category, category_id)
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
    await callback.message.edit_reply_markup(reply_markup=categories_admin_menu(items))
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
        "Yangi moderatorning Telegram ID raqamini yuboring. "
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
        if not await _authorized(callback, db, settings):
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


@router.callback_query(F.data == "admin:blocked")
async def blocked_users(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as db:
        if not await _authorized(callback, db, settings):
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
        if not await _authorized(callback, db, settings):
            return
        user = await db.scalar(select(User).where(User.anon_code == anon_code))
        if not user:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return
        code = user.anon_code
        user.is_banned = False
        user.banned_until = None
        user.ban_reason = None
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
