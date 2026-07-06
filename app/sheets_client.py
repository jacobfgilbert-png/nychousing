from __future__ import annotations

import json
import os
from typing import Protocol

from app.models import Listing


class SheetsClient(Protocol):
    def upsert_listings(self, listings: list[Listing]) -> None:
        ...


class MissingSheetsCredentials(RuntimeError):
    pass


class MemorySheetsClient:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def upsert_listings(self, listings: list[Listing]) -> None:
        existing = {row["listing_id"]: row for row in self.rows}
        for listing in listings:
            existing[listing.listing_id] = listing.as_sheet_row()
        self.rows = list(existing.values())


class RealSheetsClient:
    def __init__(self, spreadsheet_name: str, spreadsheet_id: str | None = None) -> None:
        self.spreadsheet_name = spreadsheet_name
        credentials_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        if not credentials_json:
            raise MissingSheetsCredentials("Missing Google Sheets credentials. Set GOOGLE_SHEETS_CREDENTIALS_JSON before syncing sheets.")
        self.sheets, self.drive = _build_google_services(credentials_json)
        self.spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") or self._find_or_create_spreadsheet()

    def upsert_listings(self, listings: list[Listing]) -> None:
        rows = [VISIBLE_COLUMNS + INTERNAL_COLUMNS]
        rows.extend(_row_for_listing(listing) for listing in sorted(listings, key=lambda item: item.score, reverse=True))
        self.sheets.spreadsheets().values().clear(spreadsheetId=self.spreadsheet_id, range="Listings!A:Z", body={}).execute()
        self.sheets.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range="Listings!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()
        self._hide_internal_columns()

    def _find_or_create_spreadsheet(self) -> str:
        query = f"name = '{self.spreadsheet_name.replace(chr(39), chr(92) + chr(39))}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        response = self.drive.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
        files = response.get("files", [])
        if files:
            return files[0]["id"]
        spreadsheet = self.sheets.spreadsheets().create(body={"properties": {"title": self.spreadsheet_name}, "sheets": [{"properties": {"title": "Listings"}}]}).execute()
        return spreadsheet["spreadsheetId"]

    def _hide_internal_columns(self) -> None:
        metadata = self.sheets.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        sheet_id = metadata["sheets"][0]["properties"]["sheetId"]
        start = len(VISIBLE_COLUMNS)
        end = len(VISIBLE_COLUMNS) + len(INTERNAL_COLUMNS)
        self.sheets.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateDimensionProperties": {
                            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": start, "endIndex": end},
                            "properties": {"hiddenByUser": True},
                            "fields": "hiddenByUser",
                        }
                    }
                ]
            },
        ).execute()


VISIBLE_COLUMNS = ["Score", "Status", "Price", "Area", "Dates", "Type", "Source", "Link", "Message", "Flags"]
INTERNAL_COLUMNS = ["listing_id", "commute_minutes", "commute_bucket", "contact_method", "auto_sent_at", "first_seen_at", "last_seen_at", "raw_source_id"]


def _build_google_services(credentials_json: str):
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    info = json.loads(credentials_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
    if info.get("type") == "service_account":
        credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    else:
        credentials = Credentials.from_authorized_user_info(info, scopes=scopes)
    return (
        build("sheets", "v4", credentials=credentials, cache_discovery=False),
        build("drive", "v3", credentials=credentials, cache_discovery=False),
    )


def _row_for_listing(listing: Listing) -> list:
    row = listing.as_sheet_row()
    return [row.get(column, "") for column in VISIBLE_COLUMNS + INTERNAL_COLUMNS]
