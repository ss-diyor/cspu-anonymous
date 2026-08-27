from __future__ import annotations

import asyncio
import logging

from app.main import bot, dispatcher, engine, session_factory, settings
from app.services.store import bootstrap_defaults


async def run() -> None:
    async with session_factory() as db:
        await bootstrap_defaults(db, settings)
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
