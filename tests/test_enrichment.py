from bs4 import BeautifulSoup
from app.enrichment.website import _extract_pocs
from app.enrichment import UnavailableEnrichmentProvider

def test_role_matching_and_person_specific_contacts():
    soup = BeautifulSoup("<div>Jane Doe - Founder jane@example.com 602-555-0101</div>", "html.parser")
    pocs = _extract_pocs(soup, "https://example.com/team")
    assert pocs and pocs[0].designation == "Founder"

def test_generic_contact_is_not_a_poc_email():
    soup = BeautifulSoup("<div>Jane Doe - Founder contact@example.com</div>", "html.parser")
    pocs = _extract_pocs(soup, "https://example.com/team")
    assert pocs[0].email == "Not Found"

def test_missing_external_provider_is_explicitly_unavailable():
    import asyncio
    result = asyncio.run(UnavailableEnrichmentProvider().enrich("Candle Co"))
    assert result.available is False
    assert result.employee_size == "Not Found"
    assert result.linkedin_url == "Not Found"
