import pytest
import respx
from httpx import Response

from app.discovery import OpenFactsDiscovery, WikidataDiscovery, build_discovery_plan

def test_source_planner_keeps_overpass_and_adds_free_sources():
    plans = build_discovery_plan(("overpass", "wikidata", "open_food_facts"))
    assert any(p.source == "overpass" for p in plans)
    assert any(p.source == "wikidata" and p.geographic_partition == "Arizona" for p in plans)
    assert any(p.source == "open_food_facts" and "unverified" in p.query_scope for p in plans)

def test_wikidata_query_is_small_and_arizona_scoped():
    query = WikidataDiscovery("test").build_query("cosmetics", limit=50)
    assert "wd:Q816" in query
    assert "LIMIT 50" in query
    assert "REGEX" not in query

@pytest.mark.asyncio
@respx.mock
async def test_open_facts_normalizes_records_without_claiming_arizona():
    route = respx.get("https://world.openfoodfacts.org/api/v2/search").mock(return_value=Response(200, json={"products": [{"code": "123", "brands": "Desert Coffee", "product_name": "Coffee", "link": "https://world.openfoodfacts.org/product/123"}]}))
    adapter = OpenFactsDiscovery("test", min_interval_seconds=0)
    records = await adapter.search("coffee", limit=5)
    assert route.called
    assert records[0].company_name == "Desert Coffee"
    assert records[0].hq_state == "Not Found"
