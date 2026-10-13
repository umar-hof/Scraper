import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from .source import DiscoverySource, SourceCandidate

log = logging.getLogger("hof.discovery.wikidata")

class WikidataDiscovery(DiscoverySource):
    source_name = "wikidata"
    compliance_note = "Public Wikidata SPARQL endpoint; send a descriptive User-Agent, use small queries, and respect 429/Retry-After guidance."
    endpoint = "https://query.wikidata.org/sparql"

    def __init__(self, user_agent: str, timeout: int = 30, max_retries: int = 2, min_interval_seconds: float = 5.0):
        self.headers = {"User-Agent": user_agent, "Accept": "application/sparql-results+json"}
        self.timeout, self.max_retries, self.min_interval_seconds = timeout, max(0, max_retries), min_interval_seconds
        self._last_request_at = 0.0

    def build_query(self, category: str, limit: int = 50) -> str:
        # Arizona (Q816), United States (Q30), business (Q4830453). Category is retained
        # in the query metadata; Wikidata's industry taxonomy is too sparse for a safe
        # text filter, so website evidence remains the qualification gate.
        return f'''SELECT DISTINCT ?item ?itemLabel ?website ?hqLabel WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q4830453;
        wdt:P17 wd:Q30;
        wdt:P131* wd:Q816.
  OPTIONAL {{ ?item wdt:P856 ?website. }}
  OPTIONAL {{ ?item wdt:P131 ?hq. ?hq rdfs:label ?hqLabel. FILTER(LANG(?hqLabel) = "en") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT {max(1, min(limit, 100))}'''

    async def search(self, category: str, limit: int = 50) -> list[SourceCandidate]:
        await self._wait_for_slot()
        query = self.build_query(category, limit)
        for attempt in range(1, self.max_retries + 2):
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10)), headers=self.headers) as client:
                    response = await client.get(self.endpoint, params={"query": query, "format": "json"})
                if response.status_code >= 400:
                    if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt > self.max_retries:
                        response.raise_for_status()
                    await asyncio.sleep(max(self.min_interval_seconds, min(float(response.headers.get("Retry-After", 0) or 2 ** (attempt - 1)), 60)))
                    continue
                rows = response.json().get("results", {}).get("bindings", [])
                log.info("wikidata_search category=%s status=%s duration=%.3f results=%s", category, response.status_code, time.monotonic() - started, len(rows))
                return [SourceCandidate(external_id=row["item"]["value"], company_name=row.get("itemLabel", {}).get("value", "Not Found"), source_name=self.source_name, source_url=row["item"]["value"], website=row.get("website", {}).get("value"), category=category, hq_state="Arizona", hq_city=row.get("hqLabel", {}).get("value", "Not Found"), evidence_urls=(row["item"]["value"],), evidence_notes=("Wikidata identifies a US business associated with Arizona; product and packaging evidence still required",), location_type="headquarters_or_entity") for row in rows if row.get("itemLabel")]
            except (httpx.HTTPError, ValueError) as exc:
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                log.warning("wikidata_search_error category=%s attempt=%s duration=%.3f status=%s error=%s", category, attempt, time.monotonic() - started, status, type(exc).__name__)
                if attempt > self.max_retries: raise
                await asyncio.sleep(max(self.min_interval_seconds, min(2 ** (attempt - 1), 60)))
        return []

    async def _wait_for_slot(self):
        delay = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if delay > 0: await asyncio.sleep(delay)
        self._last_request_at = time.monotonic()
