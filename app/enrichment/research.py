import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

from app.deduplication import normalize

ROLE_PATTERNS = (
    "founder", "co-founder", "owner", "ceo", "procurement manager",
    "purchasing manager", "operations manager", "supply chain manager",
    "head of operations",
)
ROLE_RE = re.compile(r"\b(" + "|".join(re.escape(role) for role in ROLE_PATTERNS) + r")\b", re.I)
NAME_RE = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})"
NAME_ROLE_RE = re.compile(NAME_RE + r"\s*(?:[-–—,|:]|\s{2,})\s*(Founder|Co-Founder|Owner|CEO|Procurement Manager|Purchasing Manager|Operations Manager|Supply Chain Manager|Head of Operations)\b", re.I)
ROLE_NAME_RE = re.compile(r"\b(Founder|Co-Founder|Owner|CEO|Procurement Manager|Purchasing Manager|Operations Manager|Supply Chain Manager|Head of Operations)\s*(?:[-–—,|:]|\s{2,})\s*" + NAME_RE, re.I)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-])\d{3}[ .-]\d{4}")
GENERIC_EMAIL_PREFIXES = {"info", "contact", "hello", "support", "sales", "admin", "office", "invent", "events", "privacy", "careers"}

@dataclass(frozen=True)
class POCEvidence:
    company_key: str
    company_name: str
    name: str
    designation: str
    department: str
    email: str = "Not Found"
    phone: str = "Not Found"
    source_url: str = "Not Found"
    extraction_method: str = "website_role_block"
    verification_status: str = "verified_role"
    captured_at: str = ""
    evidence_text: str = ""

@dataclass(frozen=True)
class ResearchQueueItem:
    company_key: str
    company_name: str
    reason: str
    suggested_queries: tuple[str, ...]
    official_source_urls: tuple[str, ...]
    status: str = "pending"

def _department(title: str) -> str:
    text = title.lower()
    if any(x in text for x in ("founder", "owner", "ceo")): return "Executive"
    if any(x in text for x in ("procurement", "purchasing")): return "Procurement"
    if "supply chain" in text: return "Supply Chain"
    return "Operations"

def _clean_name(value: str) -> str:
    return " ".join(value.strip().split())

def _usable_email(value: str) -> bool:
    return value.split("@", 1)[0].lower() not in GENERIC_EMAIL_PREFIXES

def extract_poc_evidence(company_key: str, company_name: str, page_text: str, source_url: str) -> list[POCEvidence]:
    """Extract only names and roles found together in one bounded source block."""
    results = []
    for raw_block in re.split(r"[\n|•]+", page_text):
        block = " ".join(raw_block.split())
        if not block or len(block) > 700 or not ROLE_RE.search(block): continue
        matches = []
        for match in NAME_ROLE_RE.finditer(block): matches.append((match.group(1), match.group(2)))
        for match in ROLE_NAME_RE.finditer(block): matches.append((match.group(2), match.group(1)))
        for name, designation in matches:
            name = _clean_name(name)
            if len(name.split()) < 2 or normalize(name) == normalize(company_name): continue
            emails = [email for email in EMAIL_RE.findall(block) if _usable_email(email)]
            phones = PHONE_RE.findall(block)
            results.append(POCEvidence(company_key, company_name, name, designation.title(), _department(designation), emails[0] if emails else "Not Found", phones[0] if phones else "Not Found", source_url, captured_at=datetime.now(timezone.utc).isoformat(), evidence_text=block[:500]))
    return results

def merge_poc_evidence(records: Iterable[POCEvidence]) -> list[POCEvidence]:
    """Merge same-person records; conflicting contacts are withheld, never guessed."""
    grouped: dict[tuple[str, str, str], list[POCEvidence]] = {}
    for record in records:
        grouped.setdefault((record.company_key, normalize(record.name), normalize(record.designation)), []).append(record)
    merged = []
    for group in grouped.values():
        first = group[0]
        emails = {r.email for r in group if r.email != "Not Found"}
        phones = {r.phone for r in group if r.phone != "Not Found"}
        conflict = len(emails) > 1 or len(phones) > 1
        merged.append(POCEvidence(first.company_key, first.company_name, first.name, first.designation, first.department, next(iter(emails)) if len(emails) == 1 and not conflict else "Not Found", next(iter(phones)) if len(phones) == 1 and not conflict else "Not Found", first.source_url, "merged_website_sources", "conflict" if conflict else "verified_role", first.captured_at, " | ".join(r.evidence_text for r in group)[:1000]))
    return merged

def build_manual_research_queue(company_key: str, company_name: str, official_urls: Iterable[str] = (), reason: str = "No verified POC found") -> ResearchQueueItem:
    queries = (f'"{company_name}" founder owner CEO', f'"{company_name}" procurement purchasing operations', f'"{company_name}" site:linkedin.com/in')
    return ResearchQueueItem(company_key, company_name, reason, queries, tuple(official_urls))

class PublicSourceAdapter:
    """Interface for optional public directories; disabled unless compliance is configured."""
    def __init__(self, source_name: str, terms_url: str, permitted: bool = False):
        self.source_name, self.terms_url, self.permitted = source_name, terms_url, permitted

    async def search(self, query: str) -> list[dict]:
        if not self.permitted:
            raise RuntimeError(f"{self.source_name} adapter disabled until source permission is verified: {self.terms_url}")
        return []
