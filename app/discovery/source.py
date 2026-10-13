from dataclasses import dataclass

@dataclass(frozen=True)
class SourceCandidate:
    external_id: str
    company_name: str
    source_name: str
    source_url: str
    website: str | None = None
    category: str = "Not Found"
    hq_city: str = "Not Found"
    hq_state: str = "Not Found"
    manufacturing_locations: tuple[str, ...] = ()
    retail_locations: tuple[str, ...] = ()
    evidence_urls: tuple[str, ...] = ()
    evidence_notes: tuple[str, ...] = ()
    location_type: str = "unknown"

class DiscoverySource:
    source_name = "unknown"
    compliance_note = "Source permission must be verified before enabling."
