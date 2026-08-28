from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.models import (
    Admin,
    AnonymousReply,
    AuditLog,
    Base,
    Category,
    Submission,
    SubmissionStatus,
)
from app.services.rate_limit import consume_limit
from app.services.retention import erase_user_data
from app.services.store import (
    bootstrap_defaults,
    clear_session,
    get_or_create_user,
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
        WEBHOOK_SECRET="safe_secret_1234567890_1234567890",
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


async def test_rate_limit_and_user_data_erasure() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        await bootstrap_defaults(db, make_test_settings())
        user = await get_or_create_user(db, 999)
        category = await db.scalar(select(Category).limit(1))
        submission = Submission(
            token="submission_token",
            comment_token="comment_token_1",
            user_id=user.telegram_id,
            category_id=category.id,
            content_type="text",
            text="published text",
            status=SubmissionStatus.PUBLISHED.value,
        )
        db.add(submission)
        await db.flush()
        reply = AnonymousReply(
            token="reply_token_123",
            submission_id=submission.id,
            user_id=user.telegram_id,
            content_type="text",
            text="pending reply",
            status=SubmissionStatus.PENDING.value,
        )
        db.add(reply)
        db.add(AuditLog(actor_id=999, action="submission.edited"))
        db.add(AuditLog(actor_id=999, action="inquiry.answered"))
        await db.commit()

    async with factory() as db, db.begin():
        assert await consume_limit(db, "test:user", limit=2, window_seconds=60) == 0
        assert await consume_limit(db, "test:user", limit=2, window_seconds=60) == 0
        assert await consume_limit(db, "test:user", limit=2, window_seconds=60) > 0

    async with factory() as db, db.begin():
        result = await erase_user_data(db, 999)
        assert result == {"submissions": 1, "replies": 1}

    async with factory() as db:
        assert await db.get(type(user), 999) is None
        stored_submission = await db.get(Submission, submission.id)
        stored_reply = await db.get(AnonymousReply, reply.id)
        assert stored_submission.user_id is None
        assert stored_submission.text is None
        assert stored_submission.status == SubmissionStatus.PUBLISHED.value
        assert stored_reply.user_id is None
        assert stored_reply.status == SubmissionStatus.WITHDRAWN.value
        assert list((await db.scalars(select(AuditLog.actor_id))).all()) == [None, None]

    await engine.dispose()
