import asyncio
from app.config import Settings
from app.discovery import OpenFactsDiscovery, WikidataDiscovery

async def main():
    settings = Settings()
    for name, call in (
        ("wikidata", lambda: WikidataDiscovery("HOF-Pack-Lead-Research/0.1 (ops@example.com)", 10, 0, 0).search("cosmetics", 3)),
        ("open_food_facts", lambda: OpenFactsDiscovery("HOF-Pack-Lead-Research/0.1 (ops@example.com)", settings.open_facts_base_url, 15, 1, 10).search("coffee", 3)),
    ):
        try:
            records = await call()
            print(name, len(records), [r.company_name for r in records])
        except Exception as exc:
            print(name, type(exc).__name__, str(exc))

if __name__ == "__main__": asyncio.run(main())
