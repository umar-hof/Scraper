import asyncio
from app.config import Settings
from app.enrichment import enrich_website

SITES = {
    "Yankee Candle": "https://www.yankeecandle.com/",
    "Candle Chemistry": "https://candlechemistry.com/",
    "Brite Candle Co": "https://www.britecandleco.shop/",
    "Aroma360": "https://aroma360.com/",
    "Candle Chemistry contact": "https://candlechemistry.com/pages/contact-us",
    "Brite Candle Co contact": "https://www.britecandleco.shop/contact",
    "Aroma360 contact": "https://aroma360.com/pages/contact-us",
}

async def main():
    settings = Settings()
    for company, url in SITES.items():
        result = await enrich_website(url, settings.user_agent, settings.request_timeout_seconds)
        print({"company": company, "website": url, "company_phone": result.company_phone, "email": result.email, "contact_url": result.contact_url})

if __name__ == "__main__": asyncio.run(main())
