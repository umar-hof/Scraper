from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class ProviderResult:
    employee_size: str = "Not Found"
    linkedin_url: str = "Not Found"
    source_url: str = "Not Found"
    available: bool = False
    reason: str = "provider_not_configured"

class AuthorizedEnrichmentProvider(Protocol):
    async def enrich(self, company_name: str, poc_name: str = "Not Found") -> ProviderResult: ...

class UnavailableEnrichmentProvider:
    """Safe default: no external provider means no invented enrichment."""
    async def enrich(self, company_name: str, poc_name: str = "Not Found") -> ProviderResult:
        return ProviderResult()
