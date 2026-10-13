import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import httpx

log = logging.getLogger("hof.discovery.overpass")

@dataclass(frozen=True)
class BusinessCandidate:
    name: str
    city: str
    state: str
    website: str | None
    phone: str | None
    categories: tuple[str, ...]
    source_url: str
    location_type: str = "unknown"

@dataclass(frozen=True)
class RequestReport:
    operation: str
    endpoint: str
    status_code: int | None
    duration_seconds: float
    attempts: int
    result_count: int = 0
    error: str | None = None
    method: str = "GET"
    response_excerpt: str | None = None

class OverpassRequestError(RuntimeError):
    def __init__(self, message: str, report: RequestReport):
        super().__init__(message)
        self.report = report

class OverpassDiscovery:
    """Small, polite Overpass client using bounded bounding-box queries."""
    RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
    # Public global instances used only as bounded, rate-limited fallbacks.
    # The configured endpoint is always tried first.
    FALLBACK_ENDPOINTS = (
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )

    def __init__(self, endpoint: str, user_agent: str, timeout: int = 30, max_retries: int = 3, min_interval_seconds: float = 3.0, health_ttl_seconds: int = 300):
        self.endpoint = endpoint.rstrip("/")
        self._endpoints = tuple(dict.fromkeys((self.endpoint, *self.FALLBACK_ENDPOINTS)))
        self.headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.health_ttl_seconds = max(0, health_ttl_seconds)
        self._last_request_at = 0.0
        self._health_checked_at: datetime | None = None
        self._health_ok: bool | None = None
        self.last_report: RequestReport | None = None
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10)), headers=self.headers)
        return self

    async def __aexit__(self, *_):
        if self._client: await self._client.aclose()
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use OverpassDiscovery as an async context manager")
        return self._client

    async def health_check(self, force: bool = False) -> bool:
        now = datetime.utcnow()
        if not force and self._health_checked_at and now - self._health_checked_at < timedelta(seconds=self.health_ttl_seconds):
            return bool(self._health_ok)
        started = time.monotonic()
        status_code = None
        try:
            response = await asyncio.wait_for(self.client.get(self._status_url()), timeout=min(self.timeout, 10))
            status_code = response.status_code
            # 403/406 are endpoint-policy failures, not healthy responses.
            self._health_ok = 200 <= response.status_code < 300
            return bool(self._health_ok)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            self._health_ok = False
            log.warning("overpass_health_failed endpoint=%s duration=%.3f error=%s", self.endpoint, time.monotonic() - started, type(exc).__name__)
            return False
        finally:
            self._health_checked_at = now
            body = None
            if 'response' in locals():
                body = response.text[:500].replace("\n", " ")
            self.last_report = RequestReport("health", self.endpoint, status_code, time.monotonic() - started, 1, error=None if self._health_ok else "health_check_failed", response_excerpt=body)
            log.info("overpass_health endpoint=%s status=%s duration=%.3f ok=%s", self.endpoint, status_code, time.monotonic() - started, self._health_ok)

    def _status_url(self) -> str:
        parts = urlsplit(self.endpoint)
        path = parts.path
        if path.endswith("/interpreter"): path = path[:-len("/interpreter")] + "/status"
        elif not path.endswith("/status"): path = path.rstrip("/") + "/status"
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))

    async def search(self, region: str, bbox: tuple[float, float, float, float], category: str, limit: int = 100) -> list[BusinessCandidate]:
        healthy = False
        for candidate in self._endpoints:
            if candidate != self.endpoint:
                self.endpoint = candidate
                self._health_checked_at = None
            if await self.health_check():
                healthy = True
                break
            log.warning("overpass_endpoint_unavailable endpoint=%s status=%s", self.endpoint, getattr(self.last_report, "status_code", None))
        if not healthy:
            health = self.last_report
            report = RequestReport("search", self.endpoint, health.status_code if health else None, health.duration_seconds if health else 0.0, 0, error="endpoint_health_check_failed")
            self.last_report = report
            raise OverpassRequestError("Overpass endpoint failed its health check", report)
        safe_category = re.sub(r"[^a-z0-9 _-]", "", category.lower()).strip()
        query = self.build_query(bbox, safe_category)
        started = time.monotonic()
        for attempt in range(1, self.max_retries + 2):
            await self._wait_for_slot()
            try:
                response = await self.client.post(self.endpoint, data={"data": query})
                duration = time.monotonic() - started
                status = response.status_code
                if status >= 400:
                    body = response.text[:500].replace("\n", " ")
                    report = RequestReport("search", self.endpoint, status, duration, attempt, error=f"HTTP {status}: {body}", method="POST", response_excerpt=body)
                    self.last_report = report
                    log.warning("overpass_search_failed region=%s category=%s status=%s attempt=%s duration=%.3f", region, category, status, attempt, duration)
                    if status not in self.RETRYABLE_STATUS or attempt > self.max_retries: raise OverpassRequestError(f"Overpass HTTP {status}", report)
                    await self._backoff(attempt, response)
                    continue
                records = self._normalize(response.json().get("elements", []), region, limit)
                report = RequestReport("search", self.endpoint, status, duration, attempt, len(records), method="POST")
                self.last_report = report
                log.info("overpass_search_ok region=%s category=%s status=%s attempt=%s duration=%.3f results=%s", region, category, status, attempt, duration, len(records))
                return records
            except (httpx.TimeoutException, httpx.NetworkError, ValueError) as exc:
                duration = time.monotonic() - started
                report = RequestReport("search", self.endpoint, None, duration, attempt, error=type(exc).__name__)
                self.last_report = report
                log.warning("overpass_search_error region=%s category=%s attempt=%s duration=%.3f error=%s", region, category, attempt, duration, type(exc).__name__)
                if attempt > self.max_retries: raise OverpassRequestError(str(exc), report) from exc
                await self._backoff(attempt)
        return []

    def build_query(self, bbox: tuple[float, float, float, float], safe_category: str) -> str:
        south, west, north, east = bbox
        return (f'[out:json][timeout:{max(5, min(self.timeout - 5, 60))}];'
                f'(nwr["shop"~"{re.escape(safe_category)}",i]({south},{west},{north},{east});'
                f'nwr["craft"~"{re.escape(safe_category)}",i]({south},{west},{north},{east});'
                f'nwr["description"~"{re.escape(safe_category)}",i]({south},{west},{north},{east}););'
                'out center tags;')

    async def _wait_for_slot(self):
        delay = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if delay > 0: await asyncio.sleep(delay)
        self._last_request_at = time.monotonic()

    async def _backoff(self, attempt: int, response: httpx.Response | None = None):
        retry_after = 0.0
        if response is not None:
            try: retry_after = float(response.headers.get("Retry-After", "0"))
            except ValueError: pass
        await asyncio.sleep(min(max(retry_after, 2 ** (attempt - 1)), 60.0))

    def _normalize(self, elements: list[dict], region: str, limit: int = 100) -> list[BusinessCandidate]:
        result = []
        for item in elements[:max(1, limit)]:
            tags = item.get("tags", {})
            name = tags.get("name")
            if not name: continue
            result.append(BusinessCandidate(name=name.strip(), city=region, state="Arizona", website=tags.get("website") or tags.get("contact:website"), phone=tags.get("phone") or tags.get("contact:phone"), categories=tuple(v for k, v in tags.items() if k in {"shop", "craft", "description"}), source_url=f"https://www.openstreetmap.org/{item.get('type','node')}/{item.get('id')}", location_type="retail_outlet" if tags.get("shop") else "manufacturer_or_workshop" if tags.get("craft") else "unknown"))
        return result
