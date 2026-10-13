from app.qualification import build_evidence, qualify_company

def test_private_label_evidence_qualifies_local_product_business():
    evidence = build_evidence("Arizona Candle Co", ["candles"], "Tempe", "Custom candles, private label and wholesale available", "https://example.com")
    result = qualify_company("Arizona Candle Co", ["candles"], evidence=evidence, website="https://example.com")
    assert "private-label" in result.business_types
    assert result.status == "Qualified"

def test_evidence_sources_are_preserved():
    evidence = build_evidence("Candle Co", ["candles"], "Phoenix", "Custom candles", source_urls=("https://osm.example/1", "https://example.com/about"))
    assert evidence.source_urls == ("https://osm.example/1", "https://example.com/about")
