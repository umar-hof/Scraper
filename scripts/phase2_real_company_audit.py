import asyncio
import json
from app.config import Settings
from app.deduplication import company_key, poc_key
from app.discovery import ARIZONA_REGIONS, OverpassDiscovery
from app.enrichment import enrich_company_website
from app.qualification import build_evidence, qualify_company

OFFICIAL_SITES = {
    "Yankee Candle": "https://www.yankeecandle.com/",
    "Candle Chemistry": "https://candlechemistry.com/",
    "Brite Candle Co": "https://www.britecandleco.shop/",
    "Aroma360": "https://aroma360.com/",
}

async def main():
    settings = Settings()
    async with OverpassDiscovery(settings.overpass_url, settings.user_agent, settings.request_timeout_seconds, settings.max_retries, settings.overpass_min_interval_seconds, settings.overpass_health_ttl_seconds) as discovery:
        candidates = await discovery.search("Phoenix", ARIZONA_REGIONS["Phoenix"], "candle", limit=20)
    unique = {}
    for candidate in candidates:
        unique.setdefault(company_key(candidate.name, candidate.city, candidate.state), candidate)
    print(f"REAL_NODES={len(candidates)} UNIQUE_COMPANIES={len(unique)}")
    for candidate in unique.values():
        website = candidate.website or OFFICIAL_SITES.get(candidate.name)
        enrichment = await enrich_company_website(website, settings.user_agent, settings.request_timeout_seconds, max_pages=5, min_interval_seconds=1) if website else None
        evidence = build_evidence(candidate.name, candidate.categories, candidate.city, enrichment.evidence_text if enrichment else "", website, (candidate.source_url, *(enrichment.source_urls if enrichment else ())))
        qualification = qualify_company(candidate.name, candidate.categories, evidence=evidence, website=website)
        print(json.dumps({"company": candidate.name, "source_url": candidate.source_url, "website": website or "Not Found", "score": qualification.score, "industry_score": qualification.industry_score, "status": qualification.status, "business_types": qualification.business_types, "reasons": qualification.reasons, "company_phone": enrichment.company_phone if enrichment else "Not Found", "company_email": enrichment.company_email if enrichment else "Not Found", "pocs": [p.__dict__ for p in enrichment.pocs] if enrichment else [], "employee_size": "Not Found", "linkedin": "Not Found", "source_urls": evidence.source_urls}, ensure_ascii=False))

if __name__ == "__main__": asyncio.run(main())
