from app.qualification import CompanyEvidence, qualify_company, score_business

def test_cosmetics_qualifies():
    result = qualify_company("Desert Glow Cosmetics", ["cosmetics"], evidence=CompanyEvidence(arizona_verified=True, product_business=True, packaging_evidence=True, business_types=("e-commerce",)))
    assert result.score >= 60 and result.status == "Qualified"

def test_unknown_does_not_qualify():
    assert score_business("Accounting Services", ["accounting"]).status == "Rejected"

def test_industry_score_alone_is_review_only():
    result = qualify_company("National Candle Outlet", ["candle"], evidence=CompanyEvidence(arizona_verified=True, product_business=True))
    assert result.industry_score == 88
    assert result.status == "Review"

def test_chain_retail_is_held_for_review():
    result = qualify_company("Yankee Candle", ["candles"], evidence=CompanyEvidence(arizona_verified=True, product_business=True, packaging_evidence=True, business_types=("retail",), chain_or_franchise=True, retail_only=True))
    assert result.status == "Review"

def test_missing_arizona_evidence_is_rejected():
    result = qualify_company("Desert Glow Cosmetics", ["cosmetics"], evidence=CompanyEvidence(product_business=True, packaging_evidence=True))
    assert result.status == "Rejected"

