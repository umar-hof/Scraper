import pytest

from app.config import Settings
from app.enrichment.website import CompanyEnrichment
from app.manual_seed import ManualSeed
from app.models import QualifiedLead, ResearchQueue, make_session_factory
from app.workers import Worker


@pytest.mark.asyncio
async def test_manual_seed_reuses_qualification_and_deduplicates(monkeypatch):
    async def fake_enrichment(*args, **kwargs):
        return CompanyEnrichment(evidence_text="We are a candle manufacturer based in Phoenix, Arizona. Custom packaging available.", source_urls=("https://brand.example",))

    monkeypatch.setattr("app.workers.worker.enrich_company_website", fake_enrichment)
    settings = Settings(database_url="sqlite:///:memory:", enrich_websites=True)
    factory = make_session_factory(settings)
    session = factory()
    worker = Worker(settings, factory)
    seed = ManualSeed(2, "Desert Candle Brand", "https://brand.example", "Phoenix")
    assert await worker.process_manual_seed(seed, session) == "Qualified"
    assert await worker.process_manual_seed(seed, session) == "duplicate"
    lead = session.query(QualifiedLead).one()
    assert lead.qualification_status == "Qualified"
    assert lead.poc_email_id == "Not Found"
    assert "manual_seed" in lead.evidence_json
    assert session.query(ResearchQueue).count() == 1
    session.close()
