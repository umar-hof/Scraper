import re
import unicodedata
from hashlib import sha256

def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def company_key(name: str, city: str, state: str = "Arizona") -> str:
    return sha256(f"{normalize(name)}|{normalize(city)}|{normalize(state)}".encode()).hexdigest()[:32]

def poc_key(name: str | None, email: str | None, designation: str | None) -> str:
    return sha256(f"{normalize(name or '')}|{normalize(email or '')}|{normalize(designation or '')}".encode()).hexdigest()[:32]

