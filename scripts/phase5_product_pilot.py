"""Bounded, real Open Food Facts product-first pilot.

Only URLs supplied by the product source are fetched; no search-engine result pages are used.
"""
import asyncio
import json
import re
import time
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.discovery import OpenFactsDiscovery, aggregate_product_brands, verify_arizona_context
from app.qualification.scoring import CompanyEvidence, qualify_company, infer_business_types
from app.enrichment.research import extract_poc_evidence, merge_poc_evidence


def _packaging_signal(text: str) -> bool:
    return bool(re.search(r"custom packaging|packaging|private label|wholesale|shipping boxes|branded boxes|manufactur", text, re.I))


async def fetch_official(url: str, client: httpx.AsyncClient) -> tuple[str, str | None]:
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code >= 400 or not response.text:
            return "", None
        host = (urlparse(str(response.url)).hostname or "").lower()
        if any(blocked in host for blocked in ("amazon.", "walmart.", "ebay.", "facebook.", "instagram.", "linkedin.")):
            return "", None
        return response.text[:250000], str(response.url)
    except httpx.HTTPError:
        return "", None


async def main() -> None:
    settings = Settings()
    adapter = OpenFactsDiscovery(settings.user_agent, settings.open_facts_base_url, timeout=20, max_retries=1, min_interval_seconds=6.5)
    started = time.monotonic()
    try:
        records = await adapter.search("coffee", limit=10)
    except Exception as exc:
        print(json.dumps({"source": "open_food_facts", "error": f"{type(exc).__name__}: {exc}", "duration_seconds": round(time.monotonic() - started, 3)}))
        return
    groups = aggregate_product_brands(records)
    report = {"products_retrieved": len(records), "unique_brands": len(groups), "official_websites_verified": 0, "arizona_companies_verified": 0, "qualified_packaging_prospects": 0, "verified_pocs": 0, "companies": []}
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": settings.user_agent, "Accept": "text/html,application/xhtml+xml"}) as client:
        for group in groups:
            candidate_urls = sorted(group.official_website_candidates)
            website_url, page_text = None, ""
            for url in candidate_urls:
                page_text, website_url = await fetch_official(url, client)
                if website_url:
                    break
            az_verified = verify_arizona_context(re.sub(r"<[^>]+>", " ", page_text)) if page_text else False
            pocs = []
            if page_text and website_url:
                pocs = merge_poc_evidence(extract_poc_evidence(group.normalized_name, group.canonical_name, re.sub(r"<[^>]+>", " ", page_text), website_url))
            evidence = CompanyEvidence(arizona_verified=az_verified, product_business=True, packaging_evidence=_packaging_signal(page_text), business_types=infer_business_types(group.canonical_name, page_text, website_url), source_urls=tuple(sorted(group.source_urls | ({website_url} if website_url else set()))), evidence_notes=("physical product record from Open Food Facts",), location_type="product_brand")
            qualification = qualify_company(group.canonical_name, tuple(group.product_categories), evidence=evidence, website=website_url)
            report["official_websites_verified"] += bool(website_url)
            report["arizona_companies_verified"] += az_verified
            report["qualified_packaging_prospects"] += qualification.status == "Qualified"
            report["verified_pocs"] += len(pocs)
            report["companies"].append({"brand": group.canonical_name, "products": group.product_count, "website": website_url or "Not Found", "arizona_verified": az_verified, "status": qualification.status, "score": qualification.score, "reasons": qualification.reasons, "pocs": [{"name": p.name, "designation": p.designation, "email": p.email, "phone": p.phone, "source_url": p.source_url} for p in pocs], "source_urls": sorted(group.source_urls)})
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
