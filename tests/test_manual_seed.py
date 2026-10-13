import pytest

from app.manual_seed import ManualSeedError, load_manual_seeds, normalize_website


def test_manual_seed_csv_normalizes_optional_fields():
    seeds = load_manual_seeds("examples/manual_seeds.csv")
    assert seeds[0].company_name == "Example Arizona Candle Brand"
    assert seeds[0].website_url == "https://example.com"
    assert seeds[0].arizona_location == "Phoenix"


def test_manual_seed_requires_company_name():
    with pytest.raises(ManualSeedError):
        load_manual_seeds("examples/invalid_manual_seeds.csv")


def test_manual_seed_rejects_invalid_url():
    with pytest.raises(ManualSeedError):
        normalize_website("not a url")
