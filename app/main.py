from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, Update
from fastapi import FastAPI, Header, HTTPException, Request
from sqlalchemy import text

from app.config import get_settings
from app.db import create_engine, create_session_factory
from app.handlers import admin, discussion, moderation, user
from app.services.rate_limit import TelegramRateLimitMiddleware
from app.services.retention import retention_loop
from app.services.store import bootstrap_defaults
from app.services.webhook import claim_update, finish_update

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

engine = create_engine(settings)
session_factory = create_session_factory(engine)
bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dispatcher = Dispatcher()
dispatcher["settings"] = settings
dispatcher["session_factory"] = session_factory
dispatcher.update.outer_middleware(TelegramRateLimitMiddleware(session_factory, settings))

# More specific handlers must run before the private-chat fallback handler.
dispatcher.include_router(admin.router)
dispatcher.include_router(moderation.router)
dispatcher.include_router(discussion.router)
dispatcher.include_router(user.router)


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_event = asyncio.Event()
    retention_task: asyncio.Task | None = None
    async with session_factory() as db:
        await bootstrap_defaults(db, settings)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Asosiy menyu"),
            BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
            BotCommand(command="admin", description="Admin panel"),
        ]
    )
    if settings.app_mode == "webhook":
        if not settings.webhook_url:
            raise RuntimeError(
                "WEBHOOK_BASE_URL or RAILWAY_PUBLIC_DOMAIN is required in webhook mode"
            )
        await bot.set_webhook(
            settings.webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=dispatcher.resolve_used_update_types(),
            drop_pending_updates=False,
            max_connections=settings.webhook_max_connections,
        )
        logger.info("Webhook configured at %s", settings.webhook_url)
    retention_task = asyncio.create_task(
        retention_loop(session_factory, settings, stop_event), name="retention-loop"
    )
    try:
        yield
    finally:
        stop_event.set()
        if retention_task:
            await retention_task
        await bot.session.close()
        await engine.dispose()


app = FastAPI(title="Chirchiq Anonymous Bot", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(
    x_health_secret: str | None = Header(default=None),
) -> dict[str, str]:
    supplied = x_health_secret or ""
    if not secrets.compare_digest(supplied, settings.webhook_secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    async with session_factory() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.post(settings.webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    supplied = x_telegram_bot_api_secret_token or ""
    if not secrets.compare_digest(supplied, settings.webhook_secret):
        logger.warning("webhook_auth_failed")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_webhook_body_bytes:
                raise HTTPException(status_code=413, detail="Payload too large")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > settings.max_webhook_body_bytes:
            raise HTTPException(status_code=413, detail="Payload too large")
        chunks.append(chunk)
    body = b"".join(chunks)
    try:
        update = Update.model_validate_json(body, context={"bot": bot})
    except (ValueError, TypeError) as exc:
        logger.warning("webhook_invalid_payload type=%s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from exc

    if not await claim_update(session_factory, update.update_id):
        return {"ok": True}
    try:
        await dispatcher.feed_update(bot, update)
    except Exception as exc:
        await finish_update(session_factory, update.update_id, error=type(exc).__name__)
        logger.exception("webhook_update_failed update_id=%s", update.update_id)
        raise
    await finish_update(session_factory, update.update_id)
    return {"ok": True}
