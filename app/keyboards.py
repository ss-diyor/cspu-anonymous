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
    builder.button(text="🗑 Ma’lumotlarimni o‘chirish", callback_data="user:delete_data")
    builder.adjust(1)
    return builder.as_markup()


def history_menu(pending_ids: Iterable[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for submission_id in pending_ids:
        builder.button(
            text=f"❌ #{submission_id} ni bekor qilish",
            callback_data=f"user:withdraw:{submission_id}",
        )
    builder.button(text="⬅️ Asosiy menyu", callback_data="user:home")
    builder.adjust(1)
    return builder.as_markup()


def confirm_data_deletion() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, o‘chirish", callback_data="user:delete_data_confirm")
    builder.button(text="Bekor qilish", callback_data="user:home")
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
    builder.button(text="🙋 Ko‘rib chiqishni olish", callback_data=f"sub:claim:{submission_id}")
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
    builder.adjust(1, 2, 2, 1)
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


def ban_confirmation(target: str, item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1 kun", callback_data=f"{target}:ban_confirm:{item_id}:1d")
    builder.button(text="7 kun", callback_data=f"{target}:ban_confirm:{item_id}:7d")
    builder.button(text="Doimiy", callback_data=f"{target}:ban_confirm:{item_id}:permanent")
    builder.button(text="⬅️ Bekor qilish", callback_data=f"{target}:reject_back:{item_id}")
    builder.adjust(1)
    return builder.as_markup()


def moderation_reply(reply_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🙋 Ko‘rib chiqishni olish", callback_data=f"reply:claim:{reply_id}")
    builder.button(text="✅ Tasdiqlash", callback_data=f"reply:approve:{reply_id}")
    builder.button(text="❌ Rad etish", callback_data=f"reply:reject:{reply_id}")
    builder.button(text="🚫 Bloklash", callback_data=f"reply:ban:{reply_id}")
    builder.adjust(1, 2, 1)
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


def confirm_mode_change(target: str, value: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Tasdiqlash",
        callback_data=f"admin:confirm_mode:{target}:{value}",
    )
    builder.button(text="Bekor qilish", callback_data="admin:modes")
    builder.adjust(1)
    return builder.as_markup()


def confirm_category_change(category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"admin:confirm_category:{category_id}")
    builder.button(text="Bekor qilish", callback_data="admin:categories")
    builder.adjust(1)
    return builder.as_markup()


def confirm_filter_change() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data="admin:confirm_filters")
    builder.button(text="Bekor qilish", callback_data="admin:cancel_setting")
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
