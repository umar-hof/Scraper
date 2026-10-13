from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/local.db"
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_refresh_token: str | None = None
    google_oauth_token_file: str | None = None
    google_sheet_id: str | None = None
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    user_agent: str = "HOF-Pack-Lead-Research/0.1 (ops@example.com)"
    worker_mode: str = "continuous"
    worker_concurrency: int = 1
    request_timeout_seconds: int = 30
    requests_per_minute: int = 30
    max_retries: int = 3
    overpass_min_interval_seconds: float = 3.0
    overpass_health_ttl_seconds: int = 300
    job_batch_size: int = 5
    sheets_batch_size: int = 50
    icp_qualified_threshold: int = 60
    icp_review_threshold: int = 40
    daily_request_budget: int = 1000
    enrich_websites: bool = True
    website_max_pages: int = 5
    website_min_interval_seconds: float = 1.0
    authorized_enrichment_api_key: str | None = None
    employee_size_provider_api_key: str | None = None
    linkedin_search_provider_api_key: str | None = None
    discovery_sources: str = "overpass"
    open_facts_base_url: str = "https://world.openfoodfacts.org"
    job_lease_minutes: int = 30

