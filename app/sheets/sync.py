from datetime import datetime
import json
import logging
import re
from app.models import QualifiedLead, SyncStatus
from app.deduplication import normalize
from app.sheets.auth import get_sheets_credentials

HEADERS = ["Company Name", "Designation", "POC Contact Number", "Company Contact Number", "POC Email ID", "Department", "Employee Size", "LI POC Profile"]
log = logging.getLogger("hof.sheets")

def lead_row(lead: QualifiedLead) -> list[str]:
    return [lead.company_name, lead.designation, lead.poc_contact_number, lead.company_contact_number, lead.poc_email_id, lead.department, lead.employee_size, lead.li_poc_profile]

def stable_company_identity_from_name(company_name: str) -> str:
    identity = normalize(company_name)
    return re.sub(r"\s+(incorporated|inc|llc|corp|corporation|co|company|ltd|limited)$", "", identity).strip()


def stable_company_identity(lead: QualifiedLead) -> str:
    return stable_company_identity_from_name(lead.company_name)

def _eligible_unique(leads: list[QualifiedLead]) -> list[QualifiedLead]:
    selected: dict[str, QualifiedLead] = {}
    for lead in leads:
        if lead.qualification_status != "Qualified":
            continue
        identity = stable_company_identity(lead)
        if not identity:
            continue
        current = selected.get(identity)
        if current is None or (lead.poc_email_id != "Not Found", lead.icp_score) > (current.poc_email_id != "Not Found", current.icp_score):
            selected[identity] = lead
    return list(selected.values())

class SheetsSync:
    def __init__(self, settings): self.settings = settings

    def sync(self, session, leads: list[QualifiedLead], dry_run: bool = False) -> int:
        eligible = _eligible_unique(leads)
        if dry_run:
            for lead in eligible:
                print(json.dumps({"company_identity": stable_company_identity(lead), "row": lead_row(lead)}))
            return len(eligible)
        if not self.settings.google_sheet_id:
            log.warning("google_sheets_sync_skipped reason=missing_google_sheet_id")
            return 0
        from googleapiclient.discovery import build
        creds = get_sheets_credentials(self.settings, readonly=False)
        api = build("sheets", "v4", credentials=creds, cache_discovery=False)
        spreadsheet_id = self.settings.google_sheet_id
        current = api.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range="A1:H").execute().get("values", [])
        if current and current[0] != HEADERS:
            raise ValueError("Google Sheet row 1 does not match the required eight-column header")
        if not current:
            api.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range="A1:H1", valueInputOption="RAW", body={"values": [HEADERS]}).execute()
            current = [HEADERS]
        existing_rows = {stable_company_identity_from_name(row[0]): index for index, row in enumerate(current[1:], start=2) if row and row[0].strip()}
        for lead in eligible:
            row = lead_row(lead)
            identity = stable_company_identity(lead)
            if identity in existing_rows:
                row_number = existing_rows[identity]
                api.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=f"A{row_number}:H{row_number}", valueInputOption="RAW", body={"values": [row]}).execute()
            else:
                api.spreadsheets().values().append(spreadsheetId=spreadsheet_id, range="A:H", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [row]}).execute()
        now = datetime.utcnow()
        for lead in eligible:
            receipt = session.query(SyncStatus).filter_by(lead_id=lead.id).one_or_none() or SyncStatus(lead_id=lead.id)
            receipt.state, receipt.last_synchronized_at = "synced", now
            session.add(receipt)
        session.commit()
        return len(eligible)

