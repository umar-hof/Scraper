"""Validation and normalization for operator-supplied company seeds."""

from dataclasses import dataclass
from pathlib import Path
import csv
import re
from urllib.parse import urlparse


@dataclass(frozen=True)
class ManualSeed:
    row_number: int
    company_name: str
    website_url: str | None = None
    arizona_location: str | None = None

    @property
    def source_url(self) -> str:
        return self.website_url or f"manual_seed://row/{self.row_number}"


class ManualSeedError(ValueError):
    pass


def normalize_website(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    candidate = value if "://" in value else "https://" + value
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or " " in candidate:
        raise ManualSeedError(f"invalid website URL: {value}")
    return candidate


def normalize_location(value: str | None) -> str | None:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value or None


def load_manual_seeds(path: str | Path) -> list[ManualSeed]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ManualSeedError("CSV has no header")
        fields = {field.strip().lower() for field in reader.fieldnames if field}
        if "company_name" not in fields:
            raise ManualSeedError("CSV must contain company_name")
        seeds = []
        for row_number, row in enumerate(reader, start=2):
            normalized = {(key or "").strip().lower(): (value or "") for key, value in row.items()}
            name = re.sub(r"\s+", " ", normalized.get("company_name", "").strip())
            if not name:
                raise ManualSeedError(f"row {row_number}: company_name is required")
            seeds.append(ManualSeed(row_number, name, normalize_website(normalized.get("website_url")), normalize_location(normalized.get("arizona_location"))))
    return seeds
