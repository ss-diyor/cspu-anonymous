from __future__ import annotations

from html import escape
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message, ReplyParameters

SUPPORTED_TYPES = {"text", "photo", "video", "document", "voice", "animation"}


def extract_content(message: Message) -> dict[str, Any] | None:
    if message.text:
        return {
            "content_type": "text",
            "text": message.text,
            "file_id": None,
            "file_unique_id": None,
        }
    if message.photo:
        photo = message.photo[-1]
        return {
            "content_type": "photo",
            "text": message.caption,
            "file_id": photo.file_id,
            "file_unique_id": photo.file_unique_id,
        }
    if message.video:
        return {
            "content_type": "video",
            "text": message.caption,
            "file_id": message.video.file_id,
            "file_unique_id": message.video.file_unique_id,
        }
    if message.document:
        return {
            "content_type": "document",
            "text": message.caption,
            "file_id": message.document.file_id,
            "file_unique_id": message.document.file_unique_id,
        }
    if message.voice:
        return {
            "content_type": "voice",
            "text": message.caption,
            "file_id": message.voice.file_id,
            "file_unique_id": message.voice.file_unique_id,
        }
    if message.animation:
        return {
            "content_type": "animation",
            "text": message.caption,
            "file_id": message.animation.file_id,
            "file_unique_id": message.animation.file_unique_id,
        }
    return None


def validate_content(content: dict[str, Any]) -> str | None:
    text = content.get("text") or ""
    if content["content_type"] == "text" and not text.strip():
        return "Bo‘sh xabar yuborib bo‘lmaydi."
    if content["content_type"] == "text" and len(text) > 3800:
        return "Matn 3800 belgidan oshmasligi kerak."
    if content["content_type"] != "text" and len(text) > 850:
        return "Media izohi 850 belgidan oshmasligi kerak."
    return None


def rendered_text(text: str | None, prefix: str = "", footer: str = "") -> str:
    parts = [part for part in (prefix, escape(text or ""), footer) if part]
    return "\n\n".join(parts)


async def send_content(
    bot: Bot,
    chat_id: int,
    *,
    content_type: str,
    text: str | None,
    file_id: str | None,
    prefix: str = "",
    footer: str = "",
    reply_markup: InlineKeyboardMarkup | None = None,
    reply_to_message_id: int | None = None,
    disable_notification: bool = False,
) -> Message:
    body = rendered_text(text, prefix, footer)
    reply_parameters = (
        ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
    )
    common = {
        "chat_id": chat_id,
        "reply_markup": reply_markup,
        "reply_parameters": reply_parameters,
        "disable_notification": disable_notification,
    }
    if content_type == "text":
        return await bot.send_message(text=body, **common)
    if not file_id:
        raise ValueError(f"file_id is required for {content_type}")
    if content_type == "photo":
        return await bot.send_photo(photo=file_id, caption=body or None, **common)
    if content_type == "video":
        return await bot.send_video(video=file_id, caption=body or None, **common)
    if content_type == "document":
        return await bot.send_document(document=file_id, caption=body or None, **common)
    if content_type == "voice":
        return await bot.send_voice(voice=file_id, caption=body or None, **common)
    if content_type == "animation":
        return await bot.send_animation(animation=file_id, caption=body or None, **common)
    raise ValueError(f"Unsupported content type: {content_type}")
