from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.models import Admin, Base, Category
from app.services.store import (
    bootstrap_defaults,
    clear_session,
    get_session,
    set_session,
)


def make_test_settings() -> Settings:
    return Settings(
        BOT_TOKEN="123:test",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        SUPERADMIN_IDS=123,
        CHANNEL_ID=-1001,
        MODERATION_CHAT_ID=-1002,
        DISCUSSION_CHAT_ID=-1003,
        WEBHOOK_SECRET="safe_secret_123",
    )


async def test_bootstrap_and_persistent_session() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        await bootstrap_defaults(db, make_test_settings())
        assert await db.scalar(select(func.count()).select_from(Category)) == 7
        admin = await db.get(Admin, 123)
        assert admin is not None
        assert admin.role == "superadmin"

        await set_session(db, 123, "awaiting_submission", {"category_id": 1}, 30)
        await db.commit()

    async with factory() as db, db.begin():
        current = await get_session(db, 123)
        assert current is not None
        assert current.state == "awaiting_submission"
        assert current.payload == {"category_id": 1}
        await clear_session(db, 123)

    async with factory() as db:
        assert await get_session(db, 123) is None

    await engine.dispose()
