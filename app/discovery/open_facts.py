import asyncio
import logging
import re
import time

import httpx
from urllib.parse import urlparse

from .source import DiscoverySource, SourceCandidate

log = logging.getLogger("hof.discovery.openfacts")

class OpenFactsDiscovery(DiscoverySource):
    source_name = "open_food_facts"
    compliance_note = "Open Food Facts/Open Beauty Facts read API; custom User-Agent, 10 search requests/minute, open-data attribution, and no claim of Arizona operations from product data alone."

    def __init__(self, user_agent: str, base_url: str = "https://world.openfoodfacts.org", timeout: int = 30, max_retries: int = 2, min_interval_seconds: float = 6.5):
        self.base_url = base_url.rstrip("/")
        self.headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self.timeout, self.max_retries, self.min_interval_seconds = timeout, max(0, max_retries), min_interval_seconds
        self._last_request_at = 0.0

    async def search(self, category: str, limit: int = 50) -> list[SourceCandidate]:
        await self._wait_for_slot()
        params = {"categories_tags_en": category, "countries_tags_en": "united-states", "page_size": str(max(1, min(limit, 100))), "fields": "code,product_name,brands,link,manufacturing_places,origins"}
        endpoint = f"{self.base_url}/api/v2/search"
        for attempt in range(1, self.max_retries + 2):
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10)), headers=self.headers) as client:
                    response = await client.get(endpoint, params=params)
                if response.status_code >= 400:
                    if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt > self.max_retries:
                        response.raise_for_status()
                    await asyncio.sleep(max(self.min_interval_seconds, min(float(response.headers.get("Retry-After", 0) or 2 ** (attempt - 1)), 60)))
                    continue
                products = response.json().get("products", [])
                result = []
                for product in products:
                    brand = (product.get("brands") or product.get("product_name") or "").strip()
                    if not brand: continue
                    product_url = product.get("link") or f"{self.base_url}/product/{product.get('code','')}"
                    website = self._direct_brand_website(product_url)
                    result.append(SourceCandidate(external_id=str(product.get("code", brand)), company_name=brand, source_name=self.source_name, source_url=product_url, website=website, category=category, manufacturing_locations=tuple(filter(None, (product.get("manufacturing_places") or "").split(","))), evidence_urls=(product_url, endpoint), evidence_notes=("Open product dataset identifies a US product/brand; Arizona operations and packaging relevance require independent verification",), location_type="product_record_manufacturing_unknown"))
                log.info("openfacts_search category=%s status=%s duration=%.3f results=%s", category, response.status_code, time.monotonic() - started, len(result))
                return result
            except (httpx.HTTPError, ValueError) as exc:
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                log.warning("openfacts_search_error category=%s attempt=%s duration=%.3f status=%s error=%s", category, attempt, time.monotonic() - started, status, type(exc).__name__)
                if attempt > self.max_retries: raise
                await asyncio.sleep(max(self.min_interval_seconds, min(2 ** (attempt - 1), 60)))
        return []

    def _direct_brand_website(self, url: str) -> str | None:
        """Return only a product-provided direct brand URL, never a marketplace or OFF URL."""
        try:
            parsed = urlparse(url if "://" in url else "https://" + url)
            host = (parsed.hostname or "").lower()
        except ValueError:
            return None
        blocked = ("openfoodfacts.org", "amazon.", "walmart.", "ebay.", "facebook.", "instagram.", "linkedin.")
        if not host or any(token in host for token in blocked):
            return None
        if url.startswith(("http://", "https://")):
            return url
        # OFF sometimes stores a bare official hostname; adding the scheme is URL normalization,
        # not URL discovery. It is still verified by a direct request before use.
        if re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/.*)?$", url):
            return "https://" + url
        return None

    async def _wait_for_slot(self):
        delay = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if delay > 0: await asyncio.sleep(delay)
        self._last_request_at = time.monotonic()
