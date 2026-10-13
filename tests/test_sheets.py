from types import SimpleNamespace
import pytest
from app.sheets import HEADERS, lead_row, stable_company_identity, SheetsSync

def test_exact_eight_headers_and_row():
    assert HEADERS == ["Company Name", "Designation", "POC Contact Number", "Company Contact Number", "POC Email ID", "Department", "Employee Size", "LI POC Profile"]
    row = lead_row(SimpleNamespace(company_name="A", designation="Not Found", poc_contact_number="Not Found", company_contact_number="Not Found", poc_email_id="Not Found", department="Not Found", employee_size="Not Found", li_poc_profile="Not Found"))
    assert len(row) == 8

def test_stable_identity_and_dry_run_only_include_unique_qualified(capsys):
    class Lead:
        qualification_status = "Qualified"
        company_name = " Desert Brand, LLC "
        designation = company_contact_number = poc_contact_number = poc_email_id = department = employee_size = li_poc_profile = "Not Found"
        icp_score = 80
    duplicate = Lead()
    duplicate.company_name = "Desert Brand"
    duplicate.icp_score = 70
    review = Lead()
    review.company_name = "Review Co"
    review.qualification_status = "Review"
    assert stable_company_identity(Lead()) == "desert brand"
    count = SheetsSync(type("Settings", (), {})()).sync(None, [Lead(), duplicate, review], dry_run=True)
    assert count == 1
    assert len(capsys.readouterr().out.strip().splitlines()) == 1

def test_sync_updates_existing_company_and_appends_new(monkeypatch):
    class Lead:
        qualification_status = "Qualified"
        designation = company_contact_number = poc_contact_number = poc_email_id = department = employee_size = li_poc_profile = "Not Found"
        icp_score = 80
        def __init__(self, name): self.company_name, self.id = name, 1
    existing = Lead("Existing Brand")
    new = Lead("New Brand")
    class Values:
        def __init__(self): self.updated, self.appended = [], []
        def get(self, **kwargs): return self
        def execute(self): return {"values": [HEADERS, ["Existing Brand"]]}
        def update(self, **kwargs): self.updated.append(kwargs); return self
        def append(self, **kwargs): self.appended.append(kwargs); return self
    values = Values()
    class API:
        def spreadsheets(self): return self
        def values(self): return values
    from googleapiclient import discovery
    monkeypatch.setattr("app.sheets.sync.get_sheets_credentials", lambda settings, readonly=False: object())
    monkeypatch.setattr(discovery, "build", lambda *args, **kwargs: API())
    class Query:
        def filter_by(self, **kwargs): return self
        def one_or_none(self): return None
    class Session:
        def query(self, *args): return Query()
        def add(self, value): pass
        def commit(self): pass
    settings = type("Settings", (), {"google_sheet_id": "sheet"})()
    assert SheetsSync(settings).sync(Session(), [existing, new]) == 2
    assert len(values.updated) == 1
    assert len(values.appended) == 1


def test_sync_matches_existing_company_with_suffix(monkeypatch):
    class Lead:
        qualification_status = "Qualified"
        designation = company_contact_number = poc_contact_number = poc_email_id = department = employee_size = li_poc_profile = "Not Found"
        icp_score = 80
        id = 1
        company_name = "Arizona Soap"

    class Values:
        def __init__(self): self.updated, self.appended = [], []
        def get(self, **kwargs): return self
        def execute(self): return {"values": [HEADERS, ["Arizona Soap Company"]]}
        def update(self, **kwargs): self.updated.append(kwargs); return self
        def append(self, **kwargs): self.appended.append(kwargs); return self

    values = Values()
    class API:
        def spreadsheets(self): return self
        def values(self): return values
    from googleapiclient import discovery
    monkeypatch.setattr("app.sheets.sync.get_sheets_credentials", lambda settings, readonly=False: object())
    monkeypatch.setattr(discovery, "build", lambda *args, **kwargs: API())
    class Query:
        def filter_by(self, **kwargs): return self
        def one_or_none(self): return None
    class Session:
        def query(self, *args): return Query()
        def add(self, value): pass
        def commit(self): pass
    settings = type("Settings", (), {"google_sheet_id": "sheet"})()
    assert SheetsSync(settings).sync(Session(), [Lead()]) == 1
    assert len(values.updated) == 1
    assert len(values.appended) == 0

