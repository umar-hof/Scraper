from app.enrichment import build_manual_research_queue, extract_poc_evidence, merge_poc_evidence

def test_name_title_association_and_person_contact():
    records = extract_poc_evidence("ck", "Candle Co", "Jane Doe - Founder jane.doe@example.com 602-555-0101", "https://example.com/team")
    assert len(records) == 1
    assert records[0].name == "Jane Doe"
    assert records[0].designation == "Founder"
    assert records[0].email == "jane.doe@example.com"
    assert records[0].phone == "602-555-0101"

def test_generic_company_contact_is_not_poc_contact():
    records = extract_poc_evidence("ck", "Candle Co", "Jane Doe - Founder contact@example.com", "https://example.com/team")
    assert records[0].email == "Not Found"

def test_conflicting_sources_withhold_contact_values():
    first = extract_poc_evidence("ck", "Candle Co", "Jane Doe - Founder jane@example.com", "https://example.com/about")[0]
    second = extract_poc_evidence("ck", "Candle Co", "Jane Doe - Founder jane@other.example", "https://example.com/press")[0]
    merged = merge_poc_evidence([first, second])
    assert merged[0].verification_status == "conflict"
    assert merged[0].email == "Not Found"

def test_manual_queue_is_explicit_and_source_backed():
    item = build_manual_research_queue("ck", "Candle Co", ("https://example.com/about",))
    assert item.status == "pending"
    assert "Candle Co" in item.suggested_queries[0]
    assert item.official_source_urls == ("https://example.com/about",)
