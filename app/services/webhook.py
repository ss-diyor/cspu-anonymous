from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProcessedUpdate


async def claim_update(session_factory: async_sessionmaker[AsyncSession], update_id: int) -> bool:
    now = datetime.now(UTC)
    try:
        async with session_factory() as db, db.begin():
            row = await db.get(ProcessedUpdate, update_id, with_for_update=True)
            if row is None:
                db.add(
                    ProcessedUpdate(
                        update_id=update_id,
                        status="processing",
                        attempts=1,
                        processed_at=now,
                        updated_at=now,
                    )
                )
                await db.flush()
                return True
            updated_at = row.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            if row.status == "completed":
                return False
            if row.status == "processing" and updated_at > now - timedelta(minutes=5):
                return False
            row.status = "processing"
            row.attempts += 1
            row.updated_at = now
            row.last_error = None
            return True
    except IntegrityError:
        return False


async def finish_update(
    session_factory: async_sessionmaker[AsyncSession],
    update_id: int,
    *,
    error: str | None = None,
) -> None:
    async with session_factory() as db, db.begin():
        row = await db.get(ProcessedUpdate, update_id, with_for_update=True)
        if row is None:
            return
        row.status = "failed" if error else "completed"
        row.last_error = error[:500] if error else None
        row.updated_at = datetime.now(UTC)
