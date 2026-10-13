import asyncio
import re
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

ROLE_RE = re.compile(r"\b(founder|co-founder|owner|ceo|procurement manager|purchasing manager|operations manager|supply chain manager|head of operations)\b", re.I)
PERSON_TITLE_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:[-–—,|:]\s*)\b(founder|co-founder|owner|ceo|procurement manager|purchasing manager|operations manager|supply chain manager|head of operations)\b", re.I)
TITLE_PERSON_RE = re.compile(r"\b(founder|co-founder|owner|ceo|procurement manager|purchasing manager|operations manager|supply chain manager|head of operations)\s*(?:[-–—,|:]\s*)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.I)
PHONE_RE = re.compile(r"(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-])\d{3}[ .-]\d{4}")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
GENERIC_EMAIL_PREFIXES = {"info", "contact", "hello", "support", "sales", "admin", "office", "invent", "events"}
DISCOVERY_LINK_TERMS = ("about", "team", "leadership", "contact", "our-story", "our story", "management")

@dataclass(frozen=True)
class POC:
    name: str
    designation: str
    department: str
    email: str = "Not Found"
    phone: str = "Not Found"
    source_url: str = "Not Found"
    confidence: str = "medium"
    evidence: str = ""

@dataclass(frozen=True)
class Enrichment:
    company_phone: str = "Not Found"
    email: str = "Not Found"
    contact_url: str = "Not Found"

@dataclass(frozen=True)
class CompanyEnrichment:
    company_phone: str = "Not Found"
    company_email: str = "Not Found"
    contact_url: str = "Not Found"
    pocs: tuple[POC, ...] = ()
    pages_crawled: tuple[str, ...] = ()
    evidence_text: str = ""
    source_urls: tuple[str, ...] = ()
    page_texts: tuple[tuple[str, str], ...] = ()

def _department(title: str) -> str:
    title = title.lower()
    if any(x in title for x in ("founder", "owner", "ceo")): return "Executive"
    if "procurement" in title or "purchasing" in title: return "Procurement"
    if "supply chain" in title: return "Supply Chain"
    return "Operations"

def _is_generic_email(email: str) -> bool:
    return email.split("@", 1)[0].lower() in GENERIC_EMAIL_PREFIXES

def _same_domain(url: str, root: str) -> bool:
    return urlparse(url).netloc.lower().removeprefix("www.") == urlparse(root).netloc.lower().removeprefix("www.")

def _extract_pocs(soup: BeautifulSoup, source_url: str) -> list[POC]:
    pocs = []
    for block in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "div"]):
        text = " ".join(block.get_text(" ", strip=True).split())
        if len(text) > 500 or not ROLE_RE.search(text): continue
        match = PERSON_TITLE_RE.search(text) or TITLE_PERSON_RE.search(text)
        if not match: continue
        if match.re is PERSON_TITLE_RE: name, title = match.group(1), match.group(2)
        else: title, name = match.group(1), match.group(2)
        emails = [e for e in EMAIL_RE.findall(text) if not _is_generic_email(e)]
        phones = PHONE_RE.findall(text)
        pocs.append(POC(name.strip(), title.strip().title(), _department(title), emails[0] if emails else "Not Found", phones[0] if phones else "Not Found", source_url, "high" if emails or phones else "medium", text[:500]))
    unique = {}
    for poc in pocs: unique[(poc.name.lower(), poc.designation.lower())] = poc
    return list(unique.values())

async def enrich_company_website(url: str | None, user_agent: str, timeout: int = 20, max_pages: int = 5, min_interval_seconds: float = 1.0) -> CompanyEnrichment:
    if not url: return CompanyEnrichment()
    if not url.startswith(("http://", "https://")): url = "https://" + url
    queue = deque([url])
    queued = {url}
    visited: list[str] = []
    pocs: list[POC] = []
    company_phone = company_email = contact_url = "Not Found"
    evidence = []
    page_texts = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), follow_redirects=True, headers={"User-Agent": user_agent, "Accept": "text/html"}) as client:
            while queue and len(visited) < max_pages:
                current = queue.popleft()
                if visited: await asyncio.sleep(max(0.0, min_interval_seconds))
                try:
                    response = await client.get(current)
                    response.raise_for_status()
                except (httpx.HTTPError, ValueError):
                    continue
                final_url = str(response.url)
                visited.append(final_url)
                soup = BeautifulSoup(response.text, "html.parser")
                text = soup.get_text(" ", strip=True)
                evidence.append(text[:5000])
                page_texts.append((final_url, text[:5000]))
                phones = PHONE_RE.findall(text)
                emails = [e for e in EMAIL_RE.findall(text) if not _is_generic_email(e)]
                if company_phone == "Not Found" and phones: company_phone = phones[0]
                if company_email == "Not Found":
                    all_emails = EMAIL_RE.findall(text)
                    if all_emails: company_email = all_emails[0]
                if contact_url == "Not Found" and ("contact" in final_url.lower() or "contact" in text.lower()): contact_url = final_url
                pocs.extend(_extract_pocs(soup, final_url))
                for anchor in soup.find_all("a", href=True):
                    href = urljoin(final_url, anchor["href"]).split("#", 1)[0]
                    label = f"{anchor.get_text(' ', strip=True)} {href}".lower()
                    if _same_domain(href, url) and any(term in label for term in DISCOVERY_LINK_TERMS) and href not in queued and len(queued) < max_pages * 2:
                        queued.add(href); queue.append(href)
    except (httpx.HTTPError, ValueError):
        pass
    unique = {}
    for poc in pocs: unique[(poc.name.lower(), poc.designation.lower())] = poc
    return CompanyEnrichment(company_phone, company_email, contact_url, tuple(unique.values()), tuple(visited), " ".join(evidence), tuple(visited), tuple(page_texts))

async def enrich_website(url: str | None, user_agent: str, timeout: int = 20) -> Enrichment:
    """Backward-compatible company-only enrichment wrapper."""
    result = await enrich_company_website(url, user_agent, timeout, max_pages=1)
    return Enrichment(result.company_phone, result.company_email, result.contact_url)
