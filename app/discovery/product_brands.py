"""Conservative product-to-brand normalization for public product datasets."""

from dataclasses import dataclass, field
import re
import unicodedata
from collections import OrderedDict

from .source import SourceCandidate

_CORPORATE_SUFFIXES = re.compile(r"\b(incorporated|inc|llc|l\.l\.c\.|corp|corporation|co|company|ltd|limited)\.?$", re.I)


def normalize_brand(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9& ]+", " ", text).replace("&", " and ")
    text = re.sub(r"\s+", " ", text).strip()
    previous = None
    while text and text != previous:
        previous = text
        text = _CORPORATE_SUFFIXES.sub("", text).strip(" ,.-")
    return text


def brand_parts(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"[,;|]", value or "") if normalize_brand(part))


@dataclass
class BrandAggregate:
    canonical_name: str
    normalized_name: str
    product_count: int = 0
    product_ids: set[str] = field(default_factory=set)
    source_urls: set[str] = field(default_factory=set)
    product_categories: set[str] = field(default_factory=set)
    official_website_candidates: set[str] = field(default_factory=set)
    arizona_verified: bool = False
    qualification_status: str = "Review"


def aggregate_product_brands(records: list[SourceCandidate]) -> list[BrandAggregate]:
    """Deduplicate product records while retaining evidence provenance.

    This function deliberately does not infer Arizona identity, ownership, or qualification.
    """
    groups: OrderedDict[str, BrandAggregate] = OrderedDict()
    for record in records:
        parts = brand_parts(record.company_name) or (record.company_name.strip(),)
        for part in parts:
            key = normalize_brand(part)
            if not key:
                continue
            aggregate = groups.setdefault(key, BrandAggregate(part, key))
            aggregate.product_count += 1
            aggregate.product_ids.add(record.external_id)
            aggregate.source_urls.update(record.evidence_urls or (record.source_url,))
            if record.category:
                aggregate.product_categories.add(record.category)
            if record.website:
                aggregate.official_website_candidates.add(record.website)
    return list(groups.values())


def verify_arizona_context(text: str) -> bool:
    """Require Arizona/location language in an operations context; product names alone fail."""
    lowered = re.sub(r"\s+", " ", (text or "").lower())
    if not re.search(r"\b(arizona|az|phoenix|scottsdale|tempe|tucson|mesa|chandler|flagstaff)\b", lowered):
        return False
    context = r"(based|located|headquarters|headquartered|manufactur|facility|factory|warehouse|address|contact|visit|operat)"
    return bool(re.search(rf"{context}.{{0,100}}\b(arizona|az|phoenix|scottsdale|tempe|tucson|mesa|chandler|flagstaff)\b|\b(arizona|az|phoenix|scottsdale|tempe|tucson|mesa|chandler|flagstaff)\b.{{0,100}}{context}", lowered))
