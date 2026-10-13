"""Read-only Google Sheets configuration/access check; never writes spreadsheet data."""
from app.config import Settings
from app.sheets import HEADERS
from app.sheets.auth import SheetsAuthError, get_sheets_credentials, oauth_diagnostics


def main():
    settings = Settings()
    if not settings.google_sheet_id:
        print("BLOCKED: set GOOGLE_SHEET_ID")
        raise SystemExit(2)
    from googleapiclient.discovery import build
    try:
        credentials = get_sheets_credentials(settings, readonly=True)
    except SheetsAuthError as exc:
        print(f"BLOCKED: {exc}")
        print(f"SAFE_OAUTH_DIAGNOSTICS: {oauth_diagnostics(settings)}")
        raise SystemExit(2) from exc
    api = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    try:
        metadata = api.spreadsheets().get(spreadsheetId=settings.google_sheet_id, fields="spreadsheetId,properties.title").execute()
        values = api.spreadsheets().values().get(spreadsheetId=settings.google_sheet_id, range="A1:H1").execute().get("values", [])
    except Exception as exc:
        status = getattr(getattr(exc, "resp", None), "status", "unknown")
        print(f"BLOCKED: Google Sheets read failed (HTTP {status})")
        raise SystemExit(2) from exc
    if values and values[0] != HEADERS:
        raise RuntimeError("Google Sheet header does not match the required eight columns")
    print({"read_access": True, "spreadsheet_id": metadata.get("spreadsheetId"), "title": metadata.get("properties", {}).get("title"), "header_valid": not values or values[0] == HEADERS})


if __name__ == "__main__":
    main()
