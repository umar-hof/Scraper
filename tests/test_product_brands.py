from app.discovery import SourceCandidate, aggregate_product_brands, normalize_brand, verify_arizona_context


def test_product_brand_normalization_and_deduplication():
    assert normalize_brand("Acme, Inc.") == "acme"
    records = [
        SourceCandidate("1", "Acme, Inc.", "open_food_facts", "https://off/1", category="coffee", evidence_urls=("https://off/1",)),
        SourceCandidate("2", "ACME LLC", "open_food_facts", "https://off/2", category="coffee", evidence_urls=("https://off/2",)),
    ]
    groups = aggregate_product_brands(records)
    assert len(groups) == 1
    assert groups[0].product_count == 2
    assert groups[0].arizona_verified is False


def test_product_name_arizona_false_match_is_not_operating_evidence():
    assert verify_arizona_context("Arizona Iced Tea product") is False
    assert verify_arizona_context("Based in Phoenix, Arizona; our facility ships products") is True
