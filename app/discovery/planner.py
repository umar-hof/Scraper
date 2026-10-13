from dataclasses import dataclass
from .regions import ARIZONA_REGIONS, ICP_CATEGORIES

@dataclass(frozen=True)
class DiscoveryPlan:
    source: str
    geographic_partition: str
    category: str
    query_scope: str

def build_discovery_plan(sources: tuple[str, ...] = ("overpass", "wikidata", "open_food_facts")) -> tuple[DiscoveryPlan, ...]:
    plans = []
    if "overpass" in sources:
        plans.extend(DiscoveryPlan("overpass", city, category, "bounded Arizona city box") for city in ARIZONA_REGIONS for category in ICP_CATEGORIES)
    if "wikidata" in sources:
        plans.extend(DiscoveryPlan("wikidata", "Arizona", category, "Wikidata entities linked to Arizona") for category in ICP_CATEGORIES)
    if "open_food_facts" in sources:
        plans.extend(DiscoveryPlan("open_food_facts", "United States", category, "US product records; Arizona unverified") for category in ("coffee", "tea", "food", "supplements"))
    return tuple(plans)
