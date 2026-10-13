from app.qualification import match_poc, normalize_employee_size

def test_employee_size_normalization():
    assert normalize_employee_size("11–50") == "11-50"
    assert normalize_employee_size("unknown") == "Not Found"

def test_poc_matching():
    match = match_poc("A Founder", "Founder & CEO")
    assert match and match.department == "Executive"
    assert match_poc("A Person", "Designer") is None

