from __future__ import annotations

from collections.abc import Iterable

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Category


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Anonim xabar yuborish", callback_data="user:new")
    builder.button(text="📋 Xabarlarim", callback_data="user:history")
    builder.button(text="ℹ️ Qoidalar va maxfiylik", callback_data="user:privacy")
    builder.adjust(1)
    return builder.as_markup()


def category_menu(categories: Iterable[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=f"{category.emoji} {category.title}",
            callback_data=f"category:{category.id}",
        )
    builder.button(text="❌ Bekor qilish", callback_data="user:cancel")
    builder.adjust(1)
    return builder.as_markup()


def submission_preview() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Moderatsiyaga yuborish", callback_data="draft:submit")
    builder.button(text="🔄 Qayta yozish", callback_data="draft:rewrite")
    builder.button(text="❌ Bekor qilish", callback_data="user:cancel")
    builder.adjust(1)
    return builder.as_markup()


def comment_preview() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Anonim yuborish", callback_data="comment:submit")
    builder.button(text="🔄 Qayta yozish", callback_data="comment:rewrite")
    builder.button(text="❌ Bekor qilish", callback_data="user:cancel")
    builder.adjust(1)
    return builder.as_markup()


def moderation_submission(
    submission_id: int, bot_username: str, token: str
) -> InlineKeyboardMarkup:
    username = bot_username.lstrip("@")
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"sub:approve:{submission_id}")
    builder.button(text="❌ Rad etish", callback_data=f"sub:reject:{submission_id}")
    builder.button(
        text="✏️ Tahrirlash",
        url=f"https://t.me/{username}?start=edit_{token}",
    )
    builder.button(
        text="💬 Muallifga yozish",
        url=f"https://t.me/{username}?start=ask_{token}",
    )
    builder.button(text="🚫 Bloklash", callback_data=f"sub:ban:{submission_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def rejection_reasons(target: str, item_id: int) -> InlineKeyboardMarkup:
    reasons = (
        ("rules", "Qoidalarga zid"),
        ("abuse", "Haqoratli"),
        ("spam", "Reklama yoki spam"),
        ("personal", "Shaxsiy ma’lumot mavjud"),
        ("offtopic", "Mavzuga aloqasiz"),
        ("other", "Boshqa sabab"),
    )
    builder = InlineKeyboardBuilder()
    for code, label in reasons:
        builder.button(text=label, callback_data=f"{target}:reject_reason:{item_id}:{code}")
    builder.button(text="⬅️ Orqaga", callback_data=f"{target}:reject_back:{item_id}")
    builder.adjust(1)
    return builder.as_markup()


def ban_confirmation(submission_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Ha, bloklash", callback_data=f"sub:ban_confirm:{submission_id}")
    builder.button(text="⬅️ Bekor qilish", callback_data=f"sub:reject_back:{submission_id}")
    builder.adjust(1)
    return builder.as_markup()


def moderation_reply(reply_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"reply:approve:{reply_id}")
    builder.button(text="❌ Rad etish", callback_data=f"reply:reject:{reply_id}")
    builder.button(text="🚫 Bloklash", callback_data=f"reply:ban:{reply_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


def anonymous_comment_button(bot_username: str, comment_token: str) -> InlineKeyboardMarkup:
    username = bot_username.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Anonim javob yozish",
                    style=ButtonStyle.PRIMARY,
                    url=f"https://t.me/{username}?start=comment_{comment_token}",
                )
            ]
        ]
    )


def inquiry_answer_button(bot_username: str, token: str) -> InlineKeyboardMarkup:
    username = bot_username.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Anonim javob berish",
                    url=f"https://t.me/{username}?start=answer_{token}",
                )
            ]
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Statistika", callback_data="admin:stats")
    builder.button(text="⚙️ Moderatsiya rejimi", callback_data="admin:modes")
    builder.button(text="📂 Kategoriyalar", callback_data="admin:categories")
    builder.button(text="👮 Moderatorlar", callback_data="admin:moderators")
    builder.button(text="🛡 So‘z filtrlari", callback_data="admin:filters")
    builder.button(text="🚫 Bloklanganlar", callback_data="admin:blocked")
    builder.button(text="📢 Kanal holati", callback_data="admin:channel")
    builder.button(text="🧾 Audit jurnali", callback_data="admin:audit")
    builder.button(text="🏠 Asosiy menyu", callback_data="user:home")
    builder.adjust(2, 2, 2, 1, 1, 1)
    return builder.as_markup()


def modes_menu(post_mode: str, reply_mode: str) -> InlineKeyboardMarkup:
    labels = {"manual": "Moderator", "auto": "Avtomatik", "hybrid": "Gibrid"}
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"Postlar: {labels.get(post_mode, post_mode)}",
        callback_data="admin:cycle_mode:post",
    )
    builder.button(
        text=f"Kommentlar: {labels.get(reply_mode, reply_mode)}",
        callback_data="admin:cycle_mode:reply",
    )
    builder.button(text="⬅️ Admin panel", callback_data="admin:home")
    builder.adjust(1)
    return builder.as_markup()


def categories_admin_menu(categories: Iterable[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        state = "✅" if category.enabled else "❌"
        builder.button(
            text=f"{state} {category.emoji} {category.title}",
            callback_data=f"admin:toggle_category:{category.id}",
        )
    builder.button(text="⬅️ Admin panel", callback_data="admin:home")
    builder.adjust(1)
    return builder.as_markup()


def moderators_menu(admin_ids: Iterable[int], can_manage: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_manage:
        builder.button(text="➕ Moderator qo‘shish", callback_data="admin:add_moderator")
        for admin_id in admin_ids:
            builder.button(
                text=f"➖ {admin_id}", callback_data=f"admin:remove_moderator:{admin_id}"
            )
    builder.button(text="⬅️ Admin panel", callback_data="admin:home")
    builder.adjust(1)
    return builder.as_markup()


def confirm_remove_moderator(admin_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ha, olib tashlash", callback_data=f"admin:remove_confirm:{admin_id}")
    builder.button(text="Bekor qilish", callback_data="admin:moderators")
    builder.adjust(1)
    return builder.as_markup()
