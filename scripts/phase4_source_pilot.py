import asyncio
import json
import os
from collections import Counter

from app.config import Settings
from app.deduplication import company_key
from app.discovery import ARIZONA_REGIONS, OpenFactsDiscovery, OverpassDiscovery, WikidataDiscovery
from app.enrichment import enrich_company_website
from app.qualification import build_evidence, qualify_company

async def main():
    settings = Settings()
    max_retries = int(os.getenv("PILOT_MAX_RETRIES", "0"))
    counts = Counter(); source_counts = Counter(); unique = {}
    overpass_runs = [tuple(item.split(":", 1)) for item in os.getenv("PILOT_RUNS", "Phoenix:cosmetics,Phoenix:candle,Phoenix:coffee,Tucson:cosmetics,Tucson:candle,Tucson:coffee").split(",")]
    async with OverpassDiscovery(settings.overpass_url, settings.user_agent, settings.request_timeout_seconds, max_retries, settings.overpass_min_interval_seconds, settings.overpass_health_ttl_seconds) as adapter:
        for city, category in overpass_runs:
            try:
                records = await adapter.search(city, ARIZONA_REGIONS[city], category, limit=10)
                source_counts["overpass_nodes"] += len(records)
                for record in records: unique.setdefault(company_key(record.name, record.city, record.state), record)
            except Exception as exc:
                print(json.dumps({"source": "overpass", "city": city, "category": category, "error": type(exc).__name__}))
    try:
        wikidata = WikidataDiscovery(settings.user_agent, settings.request_timeout_seconds, max_retries, min_interval_seconds=0)
        records = await wikidata.search("cosmetics", limit=10)
        source_counts["wikidata_records"] = len(records)
        print(json.dumps({"source": "wikidata", "records": len(records)}))
    except Exception as exc:
        print(json.dumps({"source": "wikidata", "error": type(exc).__name__}))
    try:
        facts = OpenFactsDiscovery(settings.user_agent, settings.open_facts_base_url, settings.request_timeout_seconds, max_retries, min_interval_seconds=0)
        records = await facts.search("coffee", limit=10)
        source_counts["open_food_facts_records"] = len(records)
        print(json.dumps({"source": "open_food_facts", "records": len(records), "arizona_verified": 0}))
    except Exception as exc:
        print(json.dumps({"source": "open_food_facts", "error": type(exc).__name__}))
    for record in list(unique.values())[:20]:
        enrichment = await enrich_company_website(record.website, settings.user_agent, settings.request_timeout_seconds, max_pages=2, min_interval_seconds=1) if record.website else None
        evidence = build_evidence(record.name, record.categories, record.city, enrichment.evidence_text if enrichment else "", record.website, (record.source_url, *(enrichment.source_urls if enrichment else ())))
        qualification = qualify_company(record.name, record.categories, evidence=evidence, website=record.website)
        counts[qualification.status] += 1
        print(json.dumps({"company": record.name, "city": record.city, "category": record.categories, "source_url": record.source_url, "status": qualification.status, "score": qualification.score, "website": record.website or "Not Found"}))
    print(json.dumps({"SOURCE_COUNTS": source_counts, "OVERPASS_UNIQUE_COMPANIES": len(unique), "OVERPASS_QUALIFICATION_COUNTS": counts, "NOTE": "No writes; Open Facts/Wikidata records are not treated as Arizona-qualified without independent evidence."}, default=dict))

if __name__ == "__main__": asyncio.run(main())
