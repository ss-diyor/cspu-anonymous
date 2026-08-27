from app.config import Settings


def make_settings(**overrides):
    values = {
        "BOT_TOKEN": "123:test",
        "DATABASE_URL": "postgres://user:pass@host/db",
        "SUPERADMIN_IDS": "12, 34",
        "CHANNEL_ID": -1001,
        "MODERATION_CHAT_ID": -1002,
        "DISCUSSION_CHAT_ID": -1003,
        "WEBHOOK_SECRET": "safe_secret-123",
        "WEBHOOK_BASE_URL": "https://example.com/",
    }
    values.update(overrides)
    return Settings(**values)


def test_database_url_is_converted_for_asyncpg() -> None:
    settings = make_settings()
    assert settings.sqlalchemy_url == "postgresql+asyncpg://user:pass@host/db"


def test_admin_ids_and_webhook_url() -> None:
    settings = make_settings()
    assert settings.superadmin_ids == frozenset({12, 34})
    assert settings.webhook_url == "https://example.com/telegram/webhook"


def test_single_admin_id_from_environment_shape() -> None:
    settings = make_settings(SUPERADMIN_IDS=12)
    assert settings.superadmin_ids == frozenset({12})
