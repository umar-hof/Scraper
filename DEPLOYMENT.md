# Deployment guide

## 1. Google Sheets

Create a Google Cloud project and enable the Google Sheets API. Create an OAuth consent screen, create OAuth credentials for a Desktop app, and retain the client ID and client secret. The application uses OAuth offline access with the minimum write scope `https://www.googleapis.com/auth/spreadsheets`. Share the target spreadsheet with the Google user who authorizes the OAuth flow. The required header is exactly: `Company Name, Designation, POC Contact Number, Company Contact Number, POC Email ID, Department, Employee Size, LI POC Profile`.

For local one-time authorization, set the Desktop App credentials and run:

```powershell
$env:GOOGLE_OAUTH_CLIENT_ID = "your-client-id"
$env:GOOGLE_OAUTH_CLIENT_SECRET = "your-client-secret"
.\.venv\Scripts\python.exe .\scripts\authorize_google_oauth.py
```

A browser opens. Approve the requested Sheets access. The refresh token is saved under `%LOCALAPPDATA%\HOF-Pack\google-oauth-token.json`; it is not printed. Copy its `refresh_token` value securely into Railway as `GOOGLE_OAUTH_REFRESH_TOKEN`. Never commit the token file or put it in the repository.

Before any write, run the read-only check:

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_sheets_access.py
```

It verifies credentials, spreadsheet access, and the existing header without writing. The sync reads existing company names, updates matching normalized identities, and appends only new qualified companies. It never syncs `Review` or `Rejected` leads. Use `python -m app.main --once --dry-run` to preview rows without a Sheets write.

If refresh fails, run this redacted diagnostic; it reports token presence/length, client-ID consistency, whitespace normalization, and OAuth error codes without printing token or secret values:

```powershell
.\.venv\Scripts\python.exe .\scripts\diagnose_google_oauth.py
```

To verify the token file locally without copying its values into shell history, load the fields in memory and run the read-only check with the real Sheet ID:

```powershell
$oauth = Get-Content "$env:LOCALAPPDATA\HOF-Pack\google-oauth-token.json" -Raw | ConvertFrom-Json
$env:GOOGLE_OAUTH_CLIENT_ID = $oauth.client_id
$env:GOOGLE_OAUTH_CLIENT_SECRET = $oauth.client_secret
$env:GOOGLE_OAUTH_REFRESH_TOKEN = $oauth.refresh_token
$env:GOOGLE_SHEET_ID = "your-spreadsheet-id"
.\.venv\Scripts\python.exe .\scripts\verify_sheets_access.py
```

The verifier refreshes with the same `spreadsheets` scope used during authorization, then performs only read operations. This avoids Google's `invalid_scope` response when a write-authorized refresh token is asked to mint a narrower read-only token.

## 2. Railway

Create a project, add PostgreSQL, and deploy this repository from GitHub or with Railway CLI. Set `DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN`, and `GOOGLE_SHEET_ID` as Railway variables. Do not use service-account JSON keys. Railway must use the previously issued refresh token; it cannot open a local browser. The Docker startup command runs `alembic upgrade head && hof-worker`. Continuous mode is the default. For finite batches set `WORKER_MODE=scheduled` and invoke `python -m app.main --once` from a Railway Cron job; do not run an endless process as Cron.

For unattended production use, the OAuth consent screen must be configured appropriately. A project in Testing can have test-user and token-lifetime restrictions; it is not a durable production posture. Move the consent screen to In production when eligible and complete any verification requirements for the scopes and app configuration. Google Workspace administrators may restrict third-party or unverified OAuth apps, so the authorizing user may need administrator approval or an internal-app configuration. A local OAuth login alone does not guarantee Railway authentication: the refresh token must be copied securely to Railway, remain valid, and be allowed by the Google account/Workspace policy. Revoked or invalid refresh tokens fail clearly and require a new local authorization.

Run migrations during deployment with `alembic upgrade head`, or allow the worker's startup migration in a controlled environment. The worker claims jobs transactionally, checkpoints cursors, and reclaims abandoned jobs after `JOB_LEASE_MINUTES`.

Phase 3 research is free by default. It crawls a bounded set of same-domain public company pages, stores only normalized POC/evidence metadata, and creates a manual research queue when no verified POC is found. It does not scrape authenticated LinkedIn, automate search-engine result pages, or enable public-directory adapters unless their terms and permission are explicitly configured. Employee size and LinkedIn remain `Not Found` without an authorized provider key.

## 3. Source and scope

The included source is the public Overpass API. It is a discovery source, not proof of ICP fit. The adapter uses Arizona place/city queries, pagination through bounded result sets, rate limiting, retries, and source attribution. Before a large pilot, review Overpass usage policy and select a mirror if needed. Paid enrichment adapters can be added behind the same interfaces; no paid service is enabled by default.

For large or repeated statewide runs, prefer a local Arizona OpenStreetMap extract instead of stressing public Overpass. Download a current Arizona `.osm.pbf` extract from a permitted provider such as Geofabrik, keep it outside the application image, and query it with a local tool such as `osmium` or a purpose-built PostGIS/pyrosm pipeline. Feed the same normalized `BusinessCandidate` records into the existing qualification and deduplication stages. Keep the city/category job checkpoints in PostgreSQL so an extract refresh or worker restart can resume without reprocessing completed partitions. The repository intentionally does not bundle a multi-gigabyte extract or heavyweight PBF dependency.

## 4. Operations

Watch Railway logs for structured JSON events, PostgreSQL size, request-budget counters, failed jobs, and Sheets sync retries. A restart is safe: `running` jobs older than the lease are returned to `retry_scheduled`; lead upserts and sync receipts are idempotent. A Sheets outage leaves leads in PostgreSQL and retries later.

## 5. Cost and security

Infrastructure costs depend on Railway's current plan and usage. The included Overpass source is generally free but rate-limited; paid provider costs are not included and require separate approval. Never commit `.env` or service-account JSON. Do not expose raw provider responses or credentials in logs.

## 6. Pilot

Start with `JOB_BATCH_SIZE=5`, one worker, and a daily request budget. Inspect a 100–200-business pilot for Arizona location, qualification, duplicates, and source evidence before increasing limits. The application does not claim statewide completeness; coverage is measured by tracked geographic jobs.

