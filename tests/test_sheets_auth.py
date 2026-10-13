import pytest

from app.config import Settings
from app.sheets.auth import SheetsAuthError, get_sheets_credentials, oauth_diagnostics


def test_oauth_missing_credentials_is_clear():
    with pytest.raises(SheetsAuthError, match="GOOGLE_OAUTH_CLIENT_ID"):
        get_sheets_credentials(Settings(google_sheet_id="sheet", google_oauth_token_file="tests/fixtures/missing-token.json"))


def test_oauth_refreshes_without_browser(monkeypatch):
    from google.oauth2 import credentials as oauth_credentials

    class FakeCredentials:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.refreshed = False
        def refresh(self, request):
            self.refreshed = True

    monkeypatch.setattr(oauth_credentials, "Credentials", FakeCredentials)
    settings = Settings(google_oauth_client_id="client", google_oauth_client_secret="secret", google_oauth_refresh_token="refresh", google_oauth_token_file="tests/fixtures/missing-token.json", google_sheet_id="sheet")
    credentials = get_sheets_credentials(settings)
    assert credentials.refreshed is True
    assert credentials.kwargs["refresh_token"] == "refresh"
    assert credentials.kwargs["scopes"] == ["https://www.googleapis.com/auth/spreadsheets"]


def test_oauth_refresh_failure_does_not_expose_token(monkeypatch):
    from google.auth.exceptions import RefreshError
    from google.oauth2 import credentials as oauth_credentials

    class FakeCredentials:
        def __init__(self, **kwargs): pass
        def refresh(self, request): raise RefreshError("invalid_grant: revoked-secret-token")

    monkeypatch.setattr(oauth_credentials, "Credentials", FakeCredentials)
    with pytest.raises(SheetsAuthError, match="code=invalid_grant") as caught:
        get_sheets_credentials(Settings(google_oauth_client_id="client", google_oauth_client_secret="secret", google_oauth_refresh_token="refresh", google_oauth_token_file="tests/fixtures/missing-token.json", google_sheet_id="sheet"))
    assert "revoked-secret-token" not in str(caught.value)


def test_oauth_diagnostics_are_redacted():
    token_path = "tests/fixtures/oauth_token.json"
    settings = Settings(google_oauth_client_id="same-client", google_oauth_client_secret="secret", google_oauth_refresh_token=' "file-secret" ', google_oauth_token_file=str(token_path))
    diagnostics = oauth_diagnostics(settings)
    assert diagnostics["token_file_has_refresh_token"] is True
    assert diagnostics["env_refresh_token_was_trimmed"] is True
    assert diagnostics["env_and_file_token_match"] is True
    assert "file-secret" not in str(diagnostics)


def test_oauth_rejects_client_mismatch():
    with pytest.raises(SheetsAuthError, match="client mismatch"):
        get_sheets_credentials(Settings(google_oauth_client_id="different-client", google_oauth_client_secret="secret", google_oauth_refresh_token="refresh", google_oauth_token_file="tests/fixtures/oauth_token.json", google_sheet_id="sheet"))
