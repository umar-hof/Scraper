import asyncio
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.config import Settings
from app.deduplication import company_key, normalize, poc_key
from app.discovery import ARIZONA_REGIONS, ICP_CATEGORIES, OpenFactsDiscovery, OverpassDiscovery, WikidataDiscovery
from app.enrichment import build_manual_research_queue, enrich_company_website, extract_poc_evidence, merge_poc_evidence
from app.models import DiscoveryJob, DiscoveryTracking, POCEvidence, QualifiedLead, ResearchQueue, SourceFailure
from app.manual_seed import ManualSeed
from app.qualification import build_evidence, qualify_company
from app.sheets import SheetsSync

log = logging.getLogger("hof.worker")
DEFAULT_CITIES = tuple(ARIZONA_REGIONS)

class Worker:
    def __init__(self, settings: Settings, session_factory):
        self.settings, self.session_factory = settings, session_factory
        self.discovery = OverpassDiscovery(settings.overpass_url, settings.user_agent, settings.request_timeout_seconds, settings.max_retries, settings.overpass_min_interval_seconds, settings.overpass_health_ttl_seconds)
        self.wikidata = WikidataDiscovery(settings.user_agent, settings.request_timeout_seconds, settings.max_retries)
        self.open_facts = OpenFactsDiscovery(settings.user_agent, settings.open_facts_base_url, settings.request_timeout_seconds, settings.max_retries)

    def seed_jobs(self, session):
        sources = tuple(s.strip() for s in self.settings.discovery_sources.split(",") if s.strip())
        if "overpass" in sources:
            for city in DEFAULT_CITIES:
                for category in ICP_CATEGORIES:
                    exists = session.query(DiscoveryJob).filter_by(geographic_partition=city, industry=category, source="overpass").first()
                    if not exists: session.add(DiscoveryJob(geographic_partition=city, industry=category, source="overpass"))
        for source, partition in (("wikidata", "Arizona"), ("open_food_facts", "United States")):
            if source not in sources: continue
            for category in ICP_CATEGORIES:
                exists = session.query(DiscoveryJob).filter_by(geographic_partition=partition, industry=category, source=source).first()
                if not exists: session.add(DiscoveryJob(geographic_partition=partition, industry=category, source=source))
        session.commit()

    async def process_manual_seed(self, seed: ManualSeed, session, source_label: str = "manual_seed") -> str:
        """Run one operator-supplied seed through the same evidence pipeline as discovery."""
        city = seed.arizona_location or "Unknown"
        state = "Arizona" if seed.arizona_location else "Unknown"
        key = company_key(seed.company_name, city, state)
        if session.query(DiscoveryTracking).filter_by(business_key=key).first():
            return "duplicate"
        if any(normalize(existing.company_name) == normalize(seed.company_name) or (seed.website_url and existing.source_url == seed.website_url) for existing in session.query(QualifiedLead).all()):
            return "duplicate"
        enrichment = await enrich_company_website(seed.website_url, self.settings.user_agent, self.settings.request_timeout_seconds, self.settings.website_max_pages, self.settings.website_min_interval_seconds) if self.settings.enrich_websites else None
        poc_evidence = merge_poc_evidence(record for url, text in (enrichment.page_texts if enrichment else ()) for record in extract_poc_evidence(key, seed.company_name, text, url))
        website_text = enrichment.evidence_text if enrichment else ""
        evidence_urls = (seed.source_url, *(enrichment.source_urls if enrichment else ()))
        combined_text = f"{seed.company_name} {website_text}".lower()
        categories = tuple(category for category in ICP_CATEGORIES if category in combined_text) or ("manual seed",)
        evidence = build_evidence(seed.company_name, categories, city, website_text, seed.website_url, evidence_urls, "manual_seed")
        qualification = qualify_company(seed.company_name, categories, evidence=evidence, website=seed.website_url)
        # A manual seed is an investigation request. Preserve incomplete evidence as Review;
        # only the existing Qualified status is eligible for Sheets export.
        stored_status = "Review" if qualification.status == "Rejected" else qualification.status
        session.add(DiscoveryTracking(business_key=key, source_url=seed.source_url, discovery_status=stored_status))
        for evidence_record in poc_evidence:
            evidence_key = poc_key(evidence_record.name, evidence_record.email, evidence_record.designation)
            if not session.query(POCEvidence).filter_by(company_key=key, poc_key=evidence_key, source_url=evidence_record.source_url).first():
                session.add(POCEvidence(company_key=key, poc_key=evidence_key, company_name=seed.company_name, poc_name=evidence_record.name, designation=evidence_record.designation, department=evidence_record.department, email=evidence_record.email, phone=evidence_record.phone, source_url=evidence_record.source_url, extraction_method=evidence_record.extraction_method, verification_status=evidence_record.verification_status))
        if stored_status != "Qualified" or not poc_evidence:
            queue_item = build_manual_research_queue(key, seed.company_name, evidence.source_urls, reason="Manual seed requires additional verified Arizona, packaging, or POC evidence")
            if not session.query(ResearchQueue).filter_by(company_key=key).first():
                session.add(ResearchQueue(company_key=key, company_name=seed.company_name, reason=queue_item.reason, suggested_queries=json.dumps(queue_item.suggested_queries), official_source_urls=json.dumps(queue_item.official_source_urls)))
        if stored_status != "Rejected":
            pocs = poc_evidence or (None,)
            for poc in pocs:
                designation = poc.designation if poc else "Not Found"
                email = poc.email if poc else "Not Found"
                company_phone = enrichment.company_phone if enrichment and enrichment.company_phone != "Not Found" else "Not Found"
                session.add(QualifiedLead(company_key=key, poc_key=poc_key(poc.name if poc else None, email, designation), poc_name=poc.name if poc else "Not Found", company_name=seed.company_name, designation=designation, department=poc.department if poc else "Not Found", poc_contact_number=poc.phone if poc else "Not Found", company_contact_number=company_phone, poc_email_id=email, icp_score=qualification.score, qualification_status=stored_status, source_url=seed.source_url, poc_source_url=poc.source_url if poc else "Not Found", business_type=",".join(qualification.business_types), evidence_json=json.dumps({"provenance": source_label, "input_row": seed.row_number, "original_qualification_status": qualification.status, "reasons": qualification.reasons, "sources": evidence.source_urls, "arizona_location_input": seed.arizona_location})))
        session.commit()
        return stored_status

    async def process_job(self, job: DiscoveryJob, session):
        job.status, job.lease_until = "running", datetime.utcnow() + timedelta(minutes=self.settings.job_lease_minutes)
        session.commit()
        if job.source == "overpass":
            candidates = await self.discovery.search(job.geographic_partition, ARIZONA_REGIONS[job.geographic_partition], job.industry)
        elif job.source == "wikidata":
            candidates = await self.wikidata.search(job.industry)
        elif job.source == "open_food_facts":
            candidates = await self.open_facts.search(job.industry)
        else:
            raise ValueError(f"Unsupported discovery source: {job.source}")
        job.cursor = f'{{"category":"{job.industry}","result_count":{len(candidates)},"completed":true}}'
        for candidate in candidates:
            if job.source == "overpass":
                name, city, state, website, source_url, categories, location_type = candidate.name, candidate.city, candidate.state, candidate.website, candidate.source_url, candidate.categories, candidate.location_type
            else:
                name = candidate.company_name
                city = candidate.hq_city if candidate.hq_state == "Arizona" else "Unknown"
                state, website, source_url, categories, location_type = candidate.hq_state, candidate.website, candidate.source_url, (job.industry,), candidate.location_type
            key = company_key(name, city, state)
            if session.query(DiscoveryTracking).filter_by(business_key=key).first(): continue
            enrichment = await enrich_company_website(website, self.settings.user_agent, self.settings.request_timeout_seconds, self.settings.website_max_pages, self.settings.website_min_interval_seconds) if self.settings.enrich_websites else None
            poc_evidence = merge_poc_evidence(record for url, text in (enrichment.page_texts if enrichment else ()) for record in extract_poc_evidence(key, name, text, url))
            website_text = enrichment.evidence_text if enrichment else ""
            evidence = build_evidence(name, categories, city, website_text, website, (source_url, *(enrichment.source_urls if enrichment else ())), location_type)
            qualification = qualify_company(name, categories, evidence=evidence, website=website)
            session.add(DiscoveryTracking(business_key=key, source_url=source_url, discovery_status=qualification.status))
            if qualification.status == "Rejected": continue
            for evidence_record in poc_evidence:
                evidence_key = poc_key(evidence_record.name, evidence_record.email, evidence_record.designation)
                if not session.query(POCEvidence).filter_by(company_key=key, poc_key=evidence_key, source_url=evidence_record.source_url).first():
                    session.add(POCEvidence(company_key=key, poc_key=evidence_key, company_name=name, poc_name=evidence_record.name, designation=evidence_record.designation, department=evidence_record.department, email=evidence_record.email, phone=evidence_record.phone, source_url=evidence_record.source_url, extraction_method=evidence_record.extraction_method, verification_status=evidence_record.verification_status))
            if not poc_evidence:
                queue_item = build_manual_research_queue(key, name, evidence.source_urls)
                if not session.query(ResearchQueue).filter_by(company_key=key).first():
                    session.add(ResearchQueue(company_key=key, company_name=name, reason=queue_item.reason, suggested_queries=json.dumps(queue_item.suggested_queries), official_source_urls=json.dumps(queue_item.official_source_urls)))
            pocs = poc_evidence or (None,)
            for poc in pocs:
                designation = poc.designation if poc else "Not Found"
                email = poc.email if poc else "Not Found"
                company_phone = enrichment.company_phone if enrichment and enrichment.company_phone != "Not Found" else (candidate.phone if job.source == "overpass" else "Not Found")
                session.add(QualifiedLead(company_key=key, poc_key=poc_key(poc.name if poc else None, email, designation), poc_name=poc.name if poc else "Not Found", company_name=name, designation=designation, department=poc.department if poc else "Not Found", poc_contact_number=poc.phone if poc else "Not Found", company_contact_number=company_phone, poc_email_id=email, icp_score=qualification.score, qualification_status=qualification.status, source_url=source_url, poc_source_url=poc.source_url if poc else "Not Found", business_type=",".join(qualification.business_types), evidence_json=json.dumps({"reasons": qualification.reasons, "sources": evidence.source_urls, "chain": evidence.chain_or_franchise, "retail_only": evidence.retail_only})))
        job.status, job.last_checkpoint, job.lease_until = "completed", datetime.utcnow(), None
        session.commit()

    async def run_once(self, dry_run: bool = False):
        session = self.session_factory()
        try:
            now = datetime.utcnow()
            session.execute(update(DiscoveryJob).where(DiscoveryJob.status == "running", DiscoveryJob.lease_until < now).values(status="retry_scheduled", lease_until=None, retry_count=DiscoveryJob.retry_count + 1))
            session.commit()
            self.seed_jobs(session)
            jobs = session.scalars(select(DiscoveryJob).where(DiscoveryJob.status.in_(["pending", "retry_scheduled"])).limit(self.settings.job_batch_size)).all()
            for job in jobs:
                try: await self.process_job(job, session)
                except Exception as exc:
                    report = getattr(exc, "report", None)
                    session.rollback()
                    session.add(SourceFailure(source=job.source, scope=f"{job.geographic_partition}:{job.industry}", status_code=getattr(report, "status_code", None), duration_seconds=getattr(report, "duration_seconds", None), error=str(exc)[:1000]))
                    job.status, job.retry_count = "retry_scheduled", job.retry_count + 1
                    session.commit()
                    log.exception("job_failed", extra={"job_id": job.id, "source": job.source, "status_code": getattr(report, "status_code", None), "duration_seconds": getattr(report, "duration_seconds", None)})
            leads = session.scalars(select(QualifiedLead).where(QualifiedLead.qualification_status == "Qualified")).all()
            SheetsSync(self.settings).sync(session, leads, dry_run=dry_run)
        finally:
            session.close()

    async def run(self, dry_run: bool = False):
        while True:
            await self.run_once(dry_run=dry_run)
            if self.settings.worker_mode == "scheduled" or dry_run: break
            await asyncio.sleep(30)
