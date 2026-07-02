from __future__ import annotations

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
    def __init__(self, spreadsheet_name: str) -> None:
        self.spreadsheet_name = spreadsheet_name
        if not os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON"):
            raise MissingSheetsCredentials("Missing Google Sheets credentials. Set GOOGLE_SHEETS_CREDENTIALS_JSON before syncing sheets.")

    def upsert_listings(self, listings: list[Listing]) -> None:
        raise NotImplementedError("Wire this thin wrapper to the Google Sheets API for production use.")

