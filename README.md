# HOF Pack Arizona Lead Engine

This project discovers Arizona businesses from the public OpenStreetMap Overpass API, qualifies product-led businesses against the HOF Pack ICP, extracts only publicly published business contact details from company websites, and synchronizes qualified rows to Google Sheets.

The system does not scrape LinkedIn, bypass access controls, guess emails, collect private contact data, or call paid providers by default. Unknown values are stored as `Not Found`. PostgreSQL is the operational source of truth; the final sheet has exactly eight requested columns.

## Quick start

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
pytest
python -m app.main --once
```

For local smoke tests without PostgreSQL, set `DATABASE_URL=sqlite:///./data/local.db`. Production should use Railway PostgreSQL.

See [DEPLOYMENT.md](DEPLOYMENT.md) for Railway, Google Cloud, credentials, recovery, and monitoring setup.

