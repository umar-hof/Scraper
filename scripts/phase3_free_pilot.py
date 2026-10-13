import asyncio
import json
import os
from collections import Counter
from app.config import Settings
from app.deduplication import company_key
from app.discovery import ARIZONA_REGIONS, OverpassDiscovery
from app.enrichment import build_manual_research_queue, enrich_company_website, extract_poc_evidence, merge_poc_evidence
from app.qualification import build_evidence, qualify_company

KNOWN_SITES = {
    "Yankee Candle": "https://www.yankeecandle.com/",
    "Candle Chemistry": "https://candlechemistry.com/",
    "Brite Candle Co": "https://www.britecandleco.shop/",
    "Aroma360": "https://aroma360.com/",
}

async def main():
    settings = Settings()
    candidates = []
    async with OverpassDiscovery(settings.overpass_url, settings.user_agent, settings.request_timeout_seconds, settings.max_retries, settings.overpass_min_interval_seconds, settings.overpass_health_ttl_seconds) as discovery:
        for category in os.getenv("PILOT_CATEGORIES", "candle,coffee,soap").split(","):
            try:
                candidates.extend(await discovery.search("Phoenix", ARIZONA_REGIONS["Phoenix"], category, limit=int(os.getenv("PILOT_LIMIT", "10"))))
            except Exception as exc:
                print(json.dumps({"category": category, "error": type(exc).__name__}))
    unique = {}
    for candidate in candidates:
        unique.setdefault(company_key(candidate.name, candidate.city, candidate.state), candidate)
    sample = list(unique.values())[:20]
    counts = Counter(); pocs_found = 0; company_contacts = 0; queue = []
    print(f"PILOT_DISCOVERED_NODES={len(candidates)} PILOT_UNIQUE_COMPANIES={len(sample)}")
    for candidate in sample:
        website = candidate.website or KNOWN_SITES.get(candidate.name)
        enrichment = await enrich_company_website(website, settings.user_agent, settings.request_timeout_seconds, max_pages=min(settings.website_max_pages, 3), min_interval_seconds=settings.website_min_interval_seconds) if website else None
        poc_records = merge_poc_evidence(r for url, text in (enrichment.page_texts if enrichment else ()) for r in extract_poc_evidence(company_key(candidate.name, candidate.city, candidate.state), candidate.name, text, url))
        evidence = build_evidence(candidate.name, candidate.categories, candidate.city, enrichment.evidence_text if enrichment else "", website, (candidate.source_url, *(enrichment.source_urls if enrichment else ())))
        qualification = qualify_company(candidate.name, candidate.categories, evidence=evidence, website=website)
        counts[qualification.status] += 1
        if poc_records: pocs_found += len(poc_records)
        if enrichment and enrichment.company_phone != "Not Found": company_contacts += 1
        if not poc_records: queue.append(build_manual_research_queue(company_key(candidate.name, candidate.city, candidate.state), candidate.name, evidence.source_urls))
        print(json.dumps({"company": candidate.name, "source_url": candidate.source_url, "status": qualification.status, "score": qualification.score, "website": website or "Not Found", "poc_count": len(poc_records), "company_phone": enrichment.company_phone if enrichment else "Not Found", "employee_size": "Not Found", "linkedin": "Not Found"}, ensure_ascii=False))
    print(json.dumps({"STATUS_COUNTS": counts, "POCS_FOUND": pocs_found, "COMPANIES_WITH_COMPANY_PHONE": company_contacts, "MANUAL_QUEUE_ITEMS": len(queue), "NOTE": "No Sheets writes; no paid APIs; employee size and LinkedIn unavailable without authorized providers."}, default=dict))

if __name__ == "__main__": asyncio.run(main())
