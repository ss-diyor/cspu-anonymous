from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import (
    AnonymousReply,
    AuditLog,
    ContentFingerprint,
    Inquiry,
    ProcessedUpdate,
    RateLimitBucket,
    Submission,
    SubmissionStatus,
    User,
    UserSession,
)

logger = logging.getLogger("security.retention")


async def erase_user_data(session: AsyncSession, telegram_id: int) -> dict[str, int]:
    submission_ids = select(Submission.id).where(Submission.user_id == telegram_id)
    await session.execute(delete(Inquiry).where(Inquiry.submission_id.in_(submission_ids)))

    reply_result = await session.execute(
        update(AnonymousReply)
        .where(AnonymousReply.user_id == telegram_id)
        .values(
            user_id=None,
            text=None,
            file_id=None,
            file_unique_id=None,
            redacted_at=datetime.now(UTC),
            status=case(
                (
                    AnonymousReply.status == SubmissionStatus.PUBLISHED.value,
                    SubmissionStatus.PUBLISHED.value,
                ),
                else_=SubmissionStatus.WITHDRAWN.value,
            ),
            rejection_reason="Foydalanuvchi ma’lumotlarini o‘chirdi",
        )
    )
    submission_result = await session.execute(
        update(Submission)
        .where(Submission.user_id == telegram_id)
        .values(
            user_id=None,
            text=None,
            file_id=None,
            file_unique_id=None,
            redacted_at=datetime.now(UTC),
            status=case(
                (
                    Submission.status == SubmissionStatus.PUBLISHED.value,
                    SubmissionStatus.PUBLISHED.value,
                ),
                else_=SubmissionStatus.WITHDRAWN.value,
            ),
            rejection_reason="Foydalanuvchi ma’lumotlarini o‘chirdi",
        )
    )
    await session.execute(
        delete(ContentFingerprint).where(ContentFingerprint.user_id == telegram_id)
    )
    await session.execute(delete(UserSession).where(UserSession.user_id == telegram_id))
    await session.execute(
        update(AuditLog)
        .where(
            AuditLog.actor_id == telegram_id,
            AuditLog.action.in_(("submission.edited", "inquiry.answered")),
        )
        .values(actor_id=None)
    )
    await session.execute(delete(User).where(User.telegram_id == telegram_id))
    return {
        "submissions": submission_result.rowcount or 0,
        "replies": reply_result.rowcount or 0,
    }


async def run_retention(session: AsyncSession, settings: Settings) -> None:
    now = datetime.now(UTC)
    rejected_before = now - timedelta(days=settings.rejected_content_retention_days)
    identity_before = now - timedelta(days=settings.identity_retention_days)

    await session.execute(
        update(Submission)
        .where(
            or_(
                Submission.created_at < identity_before,
                (
                    Submission.status.in_(
                        (
                            SubmissionStatus.REJECTED.value,
                            SubmissionStatus.WITHDRAWN.value,
                        )
                    )
                    & (Submission.created_at < rejected_before)
                ),
            ),
            Submission.redacted_at.is_(None),
        )
        .values(
            user_id=None,
            text=None,
            file_id=None,
            file_unique_id=None,
            redacted_at=now,
        )
    )
    await session.execute(
        update(AnonymousReply)
        .where(
            or_(
                AnonymousReply.created_at < identity_before,
                (
                    AnonymousReply.status.in_(
                        (
                            SubmissionStatus.REJECTED.value,
                            SubmissionStatus.WITHDRAWN.value,
                        )
                    )
                    & (AnonymousReply.created_at < rejected_before)
                ),
            ),
            AnonymousReply.redacted_at.is_(None),
        )
        .values(
            user_id=None,
            text=None,
            file_id=None,
            file_unique_id=None,
            redacted_at=now,
        )
    )

    await session.execute(delete(UserSession).where(UserSession.expires_at < now))
    await session.execute(
        delete(ContentFingerprint).where(ContentFingerprint.created_at < now - timedelta(days=7))
    )
    await session.execute(
        delete(ProcessedUpdate).where(
            ProcessedUpdate.updated_at
            < now - timedelta(days=settings.processed_update_retention_days)
        )
    )
    await session.execute(
        delete(RateLimitBucket).where(RateLimitBucket.updated_at < now - timedelta(days=2))
    )
    await session.execute(
        delete(AuditLog).where(
            AuditLog.created_at < now - timedelta(days=settings.audit_retention_days)
        )
    )

    linked_submission = exists(select(Submission.id).where(Submission.user_id == User.telegram_id))
    linked_reply = exists(
        select(AnonymousReply.id).where(AnonymousReply.user_id == User.telegram_id)
    )
    await session.execute(
        delete(User).where(
            ~linked_submission,
            ~linked_reply,
            or_(
                User.last_action_at < identity_before,
                (User.last_action_at.is_(None) & (User.created_at < identity_before)),
            ),
        )
    )


async def retention_loop(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            async with session_factory() as db, db.begin():
                await run_retention(db, settings)
        except Exception:
            logger.exception("retention_job_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=6 * 60 * 60)
        except TimeoutError:
            continue
