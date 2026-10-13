import httpx

headers = {"User-Agent": "HOF-Pack-Lead-Research/0.1 (ops@example.com)", "Accept": "application/sparql-results+json"}
query = 'SELECT ?item ?itemLabel WHERE { ?item wdt:P31/wdt:P279* wd:Q4830453; wdt:P17 wd:Q30; wdt:P131* wd:Q816. SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } LIMIT 3'
r = httpx.get("https://query.wikidata.org/sparql", params={"query": query, "format": "json"}, headers=headers, timeout=20)
print("WIKIDATA", r.status_code, r.text[:500])
r = httpx.get("https://world.openfoodfacts.org/api/v2/search", params={"categories_tags_en": "coffee", "countries_tags_en": "united-states", "page_size": 3, "fields": "code,product_name,brands,link"}, headers={"User-Agent": headers["User-Agent"]}, timeout=20)
print("OPEN_FOOD_FACTS", r.status_code, r.text[:500])
