"""Noninteractive Google OAuth refresh-token authentication for Sheets."""

import hashlib
import json
import os
import re
from pathlib import Path
from app.config import Settings

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"


class SheetsAuthError(RuntimeError):
    """Safe authentication error that never includes credentials."""


OAUTH_ERROR_CODES = ("invalid_grant", "invalid_client", "unauthorized_client", "invalid_request", "invalid_scope", "access_denied", "expired_token")


def default_token_file() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "HOF-Pack" / "google-oauth-token.json"


def _clean(value: str | None) -> str:
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


def _token_file(settings: Settings) -> Path:
    configured = getattr(settings, "google_oauth_token_file", None)
    return Path(configured).expanduser() if configured else default_token_file()


def _read_local_token(settings: Settings) -> dict:
    path = _token_file(settings)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_file_error": True}
    return data if isinstance(data, dict) else {"_file_error": True}


def _oauth_values(settings: Settings) -> tuple[str, str, str]:
    token_file = _read_local_token(settings)
    client_id = _clean(getattr(settings, "google_oauth_client_id", None) or token_file.get("client_id"))
    client_secret = _clean(getattr(settings, "google_oauth_client_secret", None) or token_file.get("client_secret"))
    refresh_token = _clean(getattr(settings, "google_oauth_refresh_token", None) or token_file.get("refresh_token"))
    if token_file.get("_file_error"):
        raise SheetsAuthError("Local OAuth token file is unreadable or invalid")
    file_client_id = _clean(token_file.get("client_id"))
    if file_client_id and client_id and file_client_id != client_id:
        raise SheetsAuthError("OAuth client mismatch between local token file and environment")
    missing = [name for name, value in (("GOOGLE_OAUTH_CLIENT_ID", client_id), ("GOOGLE_OAUTH_CLIENT_SECRET", client_secret), ("GOOGLE_OAUTH_REFRESH_TOKEN", refresh_token)) if not value]
    if missing:
        raise SheetsAuthError("Missing Google OAuth credentials: " + ", ".join(missing))
    return client_id, client_secret, refresh_token


def oauth_error_code(error: Exception) -> str:
    text = str(error).lower()
    for code in OAUTH_ERROR_CODES:
        if re.search(rf"\b{re.escape(code)}\b", text):
            return code
    for attr in ("error", "error_code"):
        value = str(getattr(error, attr, "")).lower()
        for code in OAUTH_ERROR_CODES:
            if value == code or re.search(rf"\b{re.escape(code)}\b", value):
                return code
    return "unknown"


def oauth_diagnostics(settings: Settings) -> dict:
    token_file = _read_local_token(settings)
    env_token = _clean(getattr(settings, "google_oauth_refresh_token", None))
    file_token = _clean(token_file.get("refresh_token"))
    env_client = _clean(getattr(settings, "google_oauth_client_id", None))
    file_client = _clean(token_file.get("client_id"))
    return {
        "token_file": str(_token_file(settings)),
        "token_file_readable": bool(token_file) and not token_file.get("_file_error"),
        "token_file_has_refresh_token": bool(file_token),
        "token_file_refresh_token_length": len(file_token),
        "env_refresh_token_set": bool(env_token),
        "env_refresh_token_length": len(env_token),
        "env_refresh_token_was_trimmed": bool(getattr(settings, "google_oauth_refresh_token", None)) and getattr(settings, "google_oauth_refresh_token") != env_token,
        "env_refresh_token_wrapped_in_quotes": bool(getattr(settings, "google_oauth_refresh_token", None)) and getattr(settings, "google_oauth_refresh_token").strip()[:1] in {"'", '"'},
        "env_and_file_token_match": bool(env_token and file_token) and hashlib.sha256(env_token.encode()).digest() == hashlib.sha256(file_token.encode()).digest(),
        "oauth_client_id_present": bool(env_client),
        "token_file_client_id_present": bool(file_client),
        "oauth_client_id_matches_token_file": bool(env_client and file_client and env_client == file_client),
        "authorization_scope": SHEETS_SCOPE,
        "verification_scope": SHEETS_READONLY_SCOPE,
        "scope_compatibility": "refresh uses the authorized spreadsheets scope; verification performs read-only API calls",
    }


def get_sheets_credentials(settings: Settings, *, readonly: bool = False):
    """Construct and refresh credentials without opening a browser."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    client_id, client_secret, refresh_token = _oauth_values(settings)
    # The refresh token is issued for the app's authorized scope. Requesting a
    # narrower scope here causes Google's token endpoint to return invalid_scope
    # for tokens authorized by the Desktop OAuth flow. Verification remains
    # read-only at the Sheets API operation level.
    credentials = Credentials(token=None, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token", client_id=client_id, client_secret=client_secret, scopes=[SHEETS_SCOPE])
    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        raise SheetsAuthError(f"Google OAuth refresh failed (code={oauth_error_code(exc)}); the refresh token may be revoked, expired, or unauthorized") from exc
    except Exception as exc:
        raise SheetsAuthError("Google OAuth access-token refresh failed") from exc
    return credentials
