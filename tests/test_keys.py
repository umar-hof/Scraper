from app.deduplication import company_key, poc_key

def test_company_key_normalizes():
    assert company_key("Café Co.", "Phoenix") == company_key("Cafe Co", "Phoenix", "Arizona")

def test_poc_key_stable():
    assert poc_key("A Person", "a@example.com", "Owner") == poc_key("A Person", "a@example.com", "Owner")

