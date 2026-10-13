"""One-time local browser authorization for a Google OAuth refresh token.

The token is written to a local file outside the repository. Its value is never printed.
"""
import argparse
import json
import os
import stat
from pathlib import Path

from app.sheets.auth import SHEETS_SCOPE


def default_token_file() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "HOF-Pack" / "google-oauth-token.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(default_token_file()))
    args = parser.parse_args()
    client_id = (os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise SystemExit("Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET first")
    from google_auth_oauthlib.flow import InstalledAppFlow
    config = {"installed": {"client_id": client_id, "client_secret": client_secret, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}}
    flow = InstalledAppFlow.from_client_config(config, scopes=[SHEETS_SCOPE])
    credentials = flow.run_local_server(port=0, open_browser=True, access_type="offline", prompt="consent")
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(credentials.to_json(), encoding="utf-8")
    try:
        os.chmod(output, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass
    print(f"OAuth authorization complete. Token file written to: {output}")
    print("Do not commit this file. Copy its refresh_token value securely to GOOGLE_OAUTH_REFRESH_TOKEN in Railway.")


if __name__ == "__main__":
    main()
