"""Security hardening schema.

Revision ID: 20260828_0002
Revises: 20260827_0001
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from alembic import op

from app.models import Base

revision = "20260828_0002"
down_revision = "20260827_0001"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def _add_missing_columns(table: str, columns: list[sa.Column]) -> None:
    existing = _columns(table)
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

    _add_missing_columns(
        "users",
        [sa.Column("violation_count", sa.Integer(), nullable=False, server_default="0")],
    )
    shared = [
        sa.Column("review_flags", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("claimed_by", sa.BigInteger(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redacted_at", sa.DateTime(timezone=True), nullable=True),
    ]
    _add_missing_columns("submissions", shared)
    _add_missing_columns(
        "anonymous_replies",
        [
            sa.Column("review_flags", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("claimed_by", sa.BigInteger(), nullable=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("redacted_at", sa.DateTime(timezone=True), nullable=True),
        ],
    )
    _add_missing_columns(
        "processed_updates",
        [
            sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("last_error", sa.String(length=500), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        ],
    )
    # Rows created by the previous release were already handled successfully.
    op.execute("UPDATE processed_updates SET status = 'completed'")
    op.execute("UPDATE processed_updates SET updated_at = processed_at WHERE updated_at IS NULL")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "processed_updates",
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        op.alter_column("submissions", "user_id", existing_type=sa.BigInteger(), nullable=True)
        op.alter_column(
            "anonymous_replies", "user_id", existing_type=sa.BigInteger(), nullable=True
        )


def downgrade() -> None:
    # Privacy-redaction makes user links intentionally nullable, so downgrade is
    # conservative and keeps hardened columns/data rather than risking data loss.
    pass
