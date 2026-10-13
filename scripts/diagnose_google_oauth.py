"""Print redacted OAuth configuration diagnostics; never prints secret values."""
import json
from app.config import Settings
from app.sheets.auth import oauth_diagnostics


if __name__ == "__main__":
    print(json.dumps(oauth_diagnostics(Settings()), indent=2))
