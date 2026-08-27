from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


PK = BigInteger().with_variant(Integer, "sqlite")


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


class InquiryStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    anon_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ban_reason: Mapped[str | None] = mapped_column(String(500))
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    submissions: Mapped[list[Submission]] = relationship(back_populates="user")


class Admin(Base):
    __tablename__ = "admins"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    role: Mapped[str] = mapped_column(String(20), default="moderator")
    added_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    emoji: Mapped[str] = mapped_column(String(10), default="📝")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    submissions: Mapped[list[Submission]] = relationship(back_populates="category")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    comment_token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    content_type: Mapped[str] = mapped_column(String(20))
    text: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(String(512))
    file_unique_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(20), default=SubmissionStatus.PENDING.value)
    moderation_message_id: Mapped[int | None] = mapped_column(BigInteger)
    channel_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    discussion_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    discussion_message_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger)
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="submissions")
    category: Mapped[Category] = relationship(back_populates="submissions")
    anonymous_replies: Mapped[list[AnonymousReply]] = relationship(back_populates="submission")

    __table_args__ = (Index("ix_submissions_status_created", "status", "created_at"),)


class AnonymousReply(Base):
    __tablename__ = "anonymous_replies"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"), index=True)
    content_type: Mapped[str] = mapped_column(String(20))
    text: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(String(512))
    file_unique_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(20), default=SubmissionStatus.PENDING.value)
    moderation_message_id: Mapped[int | None] = mapped_column(BigInteger)
    discussion_message_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger)
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    submission: Mapped[Submission] = relationship(back_populates="anonymous_replies")


class Inquiry(Base):
    __tablename__ = "inquiries"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=InquiryStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    state: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class BotSetting(Base):
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessedUpdate(Base):
    __tablename__ = "processed_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContentFingerprint(Base):
    __tablename__ = "content_fingerprints"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    __table_args__ = (Index("ix_fingerprint_user_created", "user_id", "created_at"),)
