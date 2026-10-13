from dataclasses import dataclass

PRIORITY = ("founder", "co-founder", "owner", "ceo", "procurement", "purchasing", "operations", "supply chain")

@dataclass(frozen=True)
class POCMatch:
    name: str
    designation: str
    department: str

def match_poc(name: str, title: str) -> POCMatch | None:
    title_l = title.lower()
    if not any(term in title_l for term in PRIORITY): return None
    department = "Executive" if any(x in title_l for x in ("founder", "owner", "ceo")) else "Operations" if "operations" in title_l else "Procurement" if any(x in title_l for x in ("procurement", "purchasing")) else "Supply Chain"
    return POCMatch(name=name, designation=title, department=department)

