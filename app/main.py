from __future__ import annotations

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
from app.services.store import bootstrap_defaults

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

# More specific handlers must run before the private-chat fallback handler.
dispatcher.include_router(admin.router)
dispatcher.include_router(moderation.router)
dispatcher.include_router(discussion.router)
dispatcher.include_router(user.router)


@asynccontextmanager
async def lifespan(_: FastAPI):
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
        )
        logger.info("Webhook configured at %s", settings.webhook_url)
    try:
        yield
    finally:
        await bot.session.close()
        await engine.dispose()


app = FastAPI(title="Chirchiq Anonymous Bot", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    async with session_factory() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post(settings.webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    supplied = x_telegram_bot_api_secret_token or ""
    if not secrets.compare_digest(supplied, settings.webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}
