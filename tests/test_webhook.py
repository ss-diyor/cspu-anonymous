from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, ProcessedUpdate
from app.services.webhook import claim_update, finish_update


async def test_webhook_update_is_idempotent_and_retryable_after_failure() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    assert await claim_update(factory, 1001)
    assert not await claim_update(factory, 1001)
    await finish_update(factory, 1001, error="temporary")
    assert await claim_update(factory, 1001)
    await finish_update(factory, 1001)
    assert not await claim_update(factory, 1001)

    async with factory() as db:
        row = await db.get(ProcessedUpdate, 1001)
        assert row.status == "completed"
        assert row.attempts == 2

    await engine.dispose()
