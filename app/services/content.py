from __future__ import annotations

import asyncio
from html import escape
from io import BytesIO
from typing import Any

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, Message, ReplyParameters
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

SUPPORTED_TYPES = {"text", "photo", "video", "document", "voice", "animation"}
MAX_FILE_SIZES = {
    "photo": 10 * 1024 * 1024,
    "video": 50 * 1024 * 1024,
    "document": 10 * 1024 * 1024,
    "voice": 20 * 1024 * 1024,
    "animation": 20 * 1024 * 1024,
}
ALLOWED_DOCUMENT_MIME_TYPES = {"application/pdf"}
MAX_PDF_PAGES = 200


def _sanitize_pdf_bytes(data: bytes) -> bytes:
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Parol bilan himoyalangan PDF qabul qilinmaydi.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF {MAX_PDF_PAGES} sahifadan oshmasligi kerak.")
        writer = PdfWriter()
        for source_page in reader.pages:
            source_page.pop("/Annots", None)
            source_page.pop("/AA", None)
            writer.add_page(source_page)
        output = BytesIO()
        writer.write(output)
        return output.getvalue()
    except PdfReadError as exc:
        raise ValueError("PDF fayl buzilgan yoki xavfsiz qayta ishlanmadi.") from exc


async def sanitized_pdf(bot: Bot, file_id: str) -> BufferedInputFile:
    source = BytesIO()
    await bot.download(file_id, destination=source)
    sanitized = await asyncio.to_thread(_sanitize_pdf_bytes, source.getvalue())
    return BufferedInputFile(sanitized, filename="anonim_hujjat.pdf")


def extract_content(message: Message) -> dict[str, Any] | None:
    if message.text:
        return {
            "content_type": "text",
            "text": message.text,
            "file_id": None,
            "file_unique_id": None,
            "file_size": None,
            "mime_type": None,
            "file_name": None,
        }
    if message.photo:
        photo = message.photo[-1]
        return {
            "content_type": "photo",
            "text": message.caption,
            "file_id": photo.file_id,
            "file_unique_id": photo.file_unique_id,
            "file_size": photo.file_size,
            "mime_type": "image/jpeg",
            "file_name": None,
        }
    if message.video:
        return {
            "content_type": "video",
            "text": message.caption,
            "file_id": message.video.file_id,
            "file_unique_id": message.video.file_unique_id,
            "file_size": message.video.file_size,
            "mime_type": message.video.mime_type,
            "file_name": message.video.file_name,
        }
    if message.document:
        return {
            "content_type": "document",
            "text": message.caption,
            "file_id": message.document.file_id,
            "file_unique_id": message.document.file_unique_id,
            "file_size": message.document.file_size,
            "mime_type": message.document.mime_type,
            "file_name": message.document.file_name,
        }
    if message.voice:
        return {
            "content_type": "voice",
            "text": message.caption,
            "file_id": message.voice.file_id,
            "file_unique_id": message.voice.file_unique_id,
            "file_size": message.voice.file_size,
            "mime_type": message.voice.mime_type,
            "file_name": None,
        }
    if message.animation:
        return {
            "content_type": "animation",
            "text": message.caption,
            "file_id": message.animation.file_id,
            "file_unique_id": message.animation.file_unique_id,
            "file_size": message.animation.file_size,
            "mime_type": message.animation.mime_type,
            "file_name": message.animation.file_name,
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
    content_type = content["content_type"]
    file_size = content.get("file_size") or 0
    limit = MAX_FILE_SIZES.get(content_type)
    if limit and file_size > limit:
        return f"Bu fayl juda katta. Maksimal hajm: {limit // (1024 * 1024)} MB."
    if content_type == "document":
        mime_type = (content.get("mime_type") or "").casefold()
        file_name = (content.get("file_name") or "").casefold()
        if mime_type not in ALLOWED_DOCUMENT_MIME_TYPES or not file_name.endswith(".pdf"):
            return "Xavfsizlik sabab faqat 10 MB gacha bo‘lgan PDF hujjat qabul qilinadi."
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
        document = await sanitized_pdf(bot, file_id)
        return await bot.send_document(document=document, caption=body or None, **common)
    if content_type == "voice":
        return await bot.send_voice(voice=file_id, caption=body or None, **common)
    if content_type == "animation":
        return await bot.send_animation(animation=file_id, caption=body or None, **common)
    raise ValueError(f"Unsupported content type: {content_type}")
