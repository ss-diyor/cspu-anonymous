from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Admin, AuditLog, BotSetting, Category, User, UserSession
from app.security import make_anon_code

DEFAULT_CATEGORIES = (
    ("suggestion", "Fikr va taklif", "💬", 10),
    ("question", "Savol", "❓", 20),
    ("problem", "Muammo", "⚠️", 30),
    ("announcement", "E’lon", "📢", 40),
    ("lost_found", "Yo‘qolgan/topilgan buyum", "🔎", 50),
    ("student_life", "Talabalar hayoti", "🎓", 60),
    ("other", "Boshqa", "📝", 70),
)

DEFAULT_SETTINGS = {
    "post_moderation_mode": "manual",
    "reply_moderation_mode": "manual",
    "banned_words": "",
    "privacy_notice_version": "1",
}


async def bootstrap_defaults(session: AsyncSession, settings: Settings) -> None:
    for key, title, emoji, sort_order in DEFAULT_CATEGORIES:
        existing = await session.scalar(select(Category).where(Category.key == key))
        if not existing:
            session.add(
                Category(key=key, title=title, emoji=emoji, sort_order=sort_order, enabled=True)
            )
    for key, value in DEFAULT_SETTINGS.items():
        existing = await session.get(BotSetting, key)
        if not existing:
            session.add(BotSetting(key=key, value=value))
    for telegram_id in settings.superadmin_ids:
        existing = await session.get(Admin, telegram_id)
        if not existing:
            session.add(Admin(telegram_id=telegram_id, role="superadmin", added_by=telegram_id))
    await session.commit()


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    user = await session.get(User, telegram_id)
    if user:
        return user
    user = User(telegram_id=telegram_id, anon_code=make_anon_code())
    session.add(user)
    await session.flush()
    return user


async def is_admin(session: AsyncSession, settings: Settings, telegram_id: int) -> bool:
    if telegram_id in settings.superadmin_ids:
        return True
    return await session.get(Admin, telegram_id) is not None


async def is_superadmin(session: AsyncSession, settings: Settings, telegram_id: int) -> bool:
    if telegram_id in settings.superadmin_ids:
        return True
    admin = await session.get(Admin, telegram_id)
    return bool(admin and admin.role == "superadmin")


async def has_admin_role(
    session: AsyncSession,
    settings: Settings,
    telegram_id: int,
    minimum_role: str,
) -> bool:
    levels = {"moderator": 10, "senior_moderator": 20, "superadmin": 30}
    if telegram_id in settings.superadmin_ids:
        role = "superadmin"
    else:
        admin = await session.get(Admin, telegram_id)
        if not admin:
            return False
        role = admin.role
    return levels.get(role, 0) >= levels.get(minimum_role, 999)


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    setting = await session.get(BotSetting, key)
    return setting.value if setting else default


async def set_setting(session: AsyncSession, key: str, value: str, actor_id: int) -> None:
    setting = await session.get(BotSetting, key)
    if setting:
        setting.value = value
        setting.updated_by = actor_id
    else:
        session.add(BotSetting(key=key, value=value, updated_by=actor_id))
    await audit(session, actor_id, "setting.changed", "setting", key, {"value": value})


async def set_session(
    session: AsyncSession,
    user_id: int,
    state: str,
    payload: dict[str, Any],
    ttl_minutes: int,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    user_session = await session.get(UserSession, user_id)
    if user_session:
        user_session.state = state
        user_session.payload = payload
        user_session.expires_at = expires_at
    else:
        session.add(
            UserSession(
                user_id=user_id,
                state=state,
                payload=payload,
                expires_at=expires_at,
            )
        )


async def get_session(
    session: AsyncSession, user_id: int, *, lock: bool = False
) -> UserSession | None:
    user_session = await session.get(UserSession, user_id, with_for_update=lock)
    if not user_session:
        return None
    expires_at = user_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        await session.delete(user_session)
        return None
    return user_session


async def clear_session(session: AsyncSession, user_id: int) -> None:
    user_session = await session.get(UserSession, user_id)
    if user_session:
        await session.delete(user_session)


async def audit(
    session: AsyncSession,
    actor_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: str | int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details or {},
        )
    )
