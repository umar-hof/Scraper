import pytest

from app.database import DatabaseConfigurationError, normalize_database_url


def test_missing_database_url_is_explicitly_rejected_for_migrations():
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is missing"):
        normalize_database_url("", require_value=True)


def test_railway_postgres_scheme_is_normalized_for_psycopg():
    assert normalize_database_url("postgres://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalize_database_url("postgresql://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"


def test_existing_driver_and_sqlite_urls_are_preserved():
    assert normalize_database_url("postgresql+psycopg://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalize_database_url("sqlite:///./data/local.db") == "sqlite:///./data/local.db"


def test_malformed_database_url_is_rejected_without_echoing_it():
    with pytest.raises(DatabaseConfigurationError, match="valid SQLAlchemy URL"):
        normalize_database_url("not-a-url", require_value=True)
