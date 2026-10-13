import asyncio
import time
import httpx
from app.config import Settings
from app.discovery import ARIZONA_REGIONS, OverpassDiscovery

async def main():
    settings = Settings()
    adapter = OverpassDiscovery(settings.overpass_url, settings.user_agent, 20, 0, 0, 0)
    query = adapter.build_query(ARIZONA_REGIONS["Phoenix"], "cosmetics")
    headers = dict(adapter.headers)
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        response = await client.post(adapter.endpoint, data={"data": query})
    print({"method": "POST", "url": adapter.endpoint, "status": response.status_code, "duration_seconds": round(time.monotonic() - started, 3), "request_headers": headers, "response_headers": dict(response.headers), "body_excerpt": response.text[:1000], "query": query})

if __name__ == "__main__": asyncio.run(main())
