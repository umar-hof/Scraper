import re

VALID_RANGES = {"1-10", "11-50", "51-200", "201-500", "500+"}

def normalize_employee_size(value: str | int | None) -> str:
    if value is None: return "Not Found"
    text = str(value).strip().lower().replace("–", "-").replace("—", "-")
    if text in {"500+", "500 plus", "500 or more"}: return "500+"
    match = re.search(r"(\d+)\s*-\s*(\d+)", text)
    if not match: return "Not Found"
    candidate = f"{int(match.group(1))}-{int(match.group(2))}"
    return candidate if candidate in VALID_RANGES else "Not Found"

