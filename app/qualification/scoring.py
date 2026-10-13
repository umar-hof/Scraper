from dataclasses import dataclass
from typing import Iterable

INDUSTRY_WEIGHTS = {"cosmetics": 92, "skincare": 92, "candle": 88, "candles": 88, "fragrance": 88, "coffee": 86, "tea": 86, "food": 86, "supplement": 84, "wellness": 84, "soap": 80, "bath": 80, "body": 80, "ecommerce": 78, "subscription": 72, "gift": 66, "bakery": 55, "restaurant": 55}
PACKAGING_TERMS = ("custom packaging", "private label", "wholesale", "packaging", "branded boxes", "shipping boxes", "custom candles", "retail packaging")
PRODUCT_TERMS = ("candle", "cosmetic", "skincare", "fragrance", "soap", "body product", "home fragrance", "coffee", "tea", "supplement", "product")
KNOWN_CHAIN_NAMES = ("yankee candle", "bath & body works", "sephora", "ulta beauty", "aroma360", "the body shop", "lush")
ARIZONA_LOCATIONS = ("arizona", "phoenix", "scottsdale", "tempe", "tucson", "mesa", "chandler", "flagstaff", "yuma", "prescott", "glendale", "gilbert")

@dataclass(frozen=True)
class CompanyEvidence:
    arizona_verified: bool = False
    product_business: bool = False
    packaging_evidence: bool = False
    business_types: tuple[str, ...] = ()
    chain_or_franchise: bool = False
    retail_only: bool = False
    purchasing_entity_identified: bool = False
    source_urls: tuple[str, ...] = ()
    evidence_notes: tuple[str, ...] = ()
    location_type: str = "unknown"

@dataclass(frozen=True)
class Qualification:
    score: int
    status: str
    industry_score: int = 0
    business_types: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

def industry_score(name: str, categories: Iterable[str] = ()) -> int:
    text = " ".join([name, *categories]).lower()
    return max((weight for word, weight in INDUSTRY_WEIGHTS.items() if word in text), default=0)

def infer_business_types(name: str, website_text: str = "", website_url: str | None = None) -> tuple[str, ...]:
    text = f"{name} {website_text}".lower()
    types = []
    if any(x in text for x in ("private label", "wholesale", "custom candles", "custom product")): types.append("private-label")
    if any(x in text for x in ("manufacturer", "manufacturing", "made in", "we make", "our products")): types.append("manufacturer")
    if website_url or any(x in text for x in ("shop online", "add to cart", "shipping", "shop collection")): types.append("e-commerce")
    if any(x in text for x in ("store", "showroom", "retail", "locations")): types.append("retail")
    if not types: types.append("unknown")
    return tuple(dict.fromkeys(types))

def build_evidence(name: str, categories: Iterable[str], city: str, website_text: str = "", website_url: str | None = None, source_urls: Iterable[str] = (), location_type: str = "unknown") -> CompanyEvidence:
    text = f"{name} {' '.join(categories)} {website_text}".lower()
    types = infer_business_types(name, website_text, website_url)
    chain = any(hint in name.lower() for hint in KNOWN_CHAIN_NAMES) or "franchise" in text
    retail_only = "retail" in types and not any(t in types for t in ("manufacturer", "private-label", "e-commerce"))
    packaging = any(term in text for term in PACKAGING_TERMS)
    product = any(term in text for term in PRODUCT_TERMS)
    notes = []
    if product: notes.append("product-business evidence")
    if packaging: notes.append("custom/recurring packaging signal")
    if chain: notes.append("chain/brand signal")
    if retail_only: notes.append("retail-only signal")
    explicit_location = city not in {"", "Unknown", "Not Found"}
    location_text = website_text.lower()
    location_context = any(place in location_text for place in ARIZONA_LOCATIONS) and any(term in location_text for term in ("based", "located", "headquarters", "headquartered", "manufactur", "facility", "factory", "warehouse", "address", "contact", "visit", "operate"))
    arizona_verified = explicit_location or location_context
    if location_context and not explicit_location:
        notes.append("Arizona operations evidence found on official website")
    return CompanyEvidence(arizona_verified, product, packaging, types, chain, retail_only, False, tuple(source_urls), tuple(notes), location_type)

def qualify_company(name: str, categories: Iterable[str] = (), *, evidence: CompanyEvidence | None = None, employee_size: str | None = None, revenue: float | None = None, website: str | None = None) -> Qualification:
    evidence = evidence or CompanyEvidence()
    base = industry_score(name, categories)
    score = base
    reasons = list(evidence.evidence_notes)
    if evidence.arizona_verified: score += 5
    if evidence.product_business: score += 4
    if evidence.packaging_evidence: score += 5
    if any(t in evidence.business_types for t in ("manufacturer", "private-label", "e-commerce")): score += 4
    if employee_size in {"2-50", "11-50", "51-200"}: score += 5
    if revenue is not None and 250_000 <= revenue <= 10_000_000: score += 5
    if website: score += 2
    score = min(score, 100)
    if base < 40 or not evidence.arizona_verified or not evidence.product_business:
        status = "Rejected"
    elif evidence.chain_or_franchise and evidence.retail_only and not evidence.purchasing_entity_identified:
        status = "Review"
        reasons.append("chain retail location requires purchasing-entity evidence")
    elif not evidence.packaging_evidence:
        status = "Review"
        reasons.append("packaging-need evidence is not yet verified")
    else:
        status = "Qualified"
    return Qualification(score, status, base, evidence.business_types, tuple(dict.fromkeys(reasons)))

def score_business(name: str, categories: Iterable[str] = (), employee_size: str | None = None, revenue: float | None = None, website: str | None = None) -> Qualification:
    """Compatibility wrapper: industry score alone is never enough for Qualified."""
    evidence = CompanyEvidence(product_business=industry_score(name, categories) > 0, source_urls=(website,) if website else ())
    return qualify_company(name, categories, evidence=evidence, employee_size=employee_size, revenue=revenue, website=website)
