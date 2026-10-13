import asyncio
import os
from app.config import Settings
from app.discovery import ARIZONA_REGIONS, OverpassDiscovery, OverpassRequestError
from app.deduplication import company_key
from app.qualification import score_business

async def main():
    settings = Settings()
    city = os.getenv("DISCOVERY_CITY", "Phoenix")
    keywords = os.getenv("DISCOVERY_KEYWORDS", "cosmetics,candle,coffee,tea,gift,soap").split(",")
    try:
        async with OverpassDiscovery(settings.overpass_url, settings.user_agent, settings.request_timeout_seconds, settings.max_retries, settings.overpass_min_interval_seconds, settings.overpass_health_ttl_seconds) as adapter:
            records = await adapter.search(city, ARIZONA_REGIONS[city], keywords[0], limit=20)
            report = adapter.last_report
    except OverpassRequestError as exc:
        print(f"LIVE_DISCOVERY_BLOCKED={exc}")
        print(f"REQUEST_REPORT={exc.report}")
        return
    print(f"LIVE_RECORD_COUNT={len(records)}")
    print(f"REQUEST_REPORT={report}")
    seen = set()
    for record in records[:20]:
        key = company_key(record.name, record.city, record.state)
        qualification = score_business(record.name, record.categories, website=record.website)
        print({"company_name": record.name, "city": record.city, "state": record.state, "website": record.website or "Not Found", "phone": record.phone or "Not Found", "categories": record.categories, "source_url": record.source_url, "icp_score": qualification.score, "qualification_status": qualification.status, "dedupe_key_unique": key not in seen})
        seen.add(key)
    print(f"UNIQUE_KEYS={len(seen)}")

if __name__ == "__main__":
    asyncio.run(main())

