"""Database URL normalization shared by the app and Alembic."""

from __future__ import annotations

import re


class DatabaseConfigurationError(RuntimeError):
    """Raised when the deployment database setting cannot be used."""


_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def normalize_database_url(raw_url: str | None, *, require_value: bool = False) -> str:
    """Return a SQLAlchemy-compatible URL without exposing credentials.

    Railway may expose PostgreSQL URLs as ``postgres://``. SQLAlchemy 2 with
    psycopg requires an explicit supported PostgreSQL scheme, so both common
    PostgreSQL forms are normalized to the installed psycopg driver.
    """

    value = (raw_url or "").strip()
    if not value:
        if require_value:
            raise DatabaseConfigurationError(
                "DATABASE_URL is missing or empty. Attach a Railway PostgreSQL "
                "service and add its DATABASE_URL as a reference variable."
            )
        return value

    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://") :]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://") :]

    if not _SCHEME_RE.match(value):
        raise DatabaseConfigurationError(
            "DATABASE_URL is not a valid SQLAlchemy URL. Use a Railway PostgreSQL "
            "connection string such as postgresql://..."
        )
    return value
