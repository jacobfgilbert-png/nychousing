from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    NEW = "new"
    NEEDS_MANUAL_SEND = "needs_manual_send"
    AUTO_SENT = "auto_sent"
    CONTACTED = "contacted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


FLAGS = {
    "check_location",
    "check_commute",
    "check_dates",
    "check_price",
    "check_furnished",
    "scam_risk",
    "missing_contact",
}


@dataclass
class RawEmail:
    raw_source_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime


@dataclass
class Listing:
    source: str = "manual"
    title: str = ""
    description: str = ""
    url: str = ""
    source_listing_id: str | None = None
    price: int | None = None
    available_from: date | None = None
    available_to: date | None = None
    min_stay_days: int | None = None
    max_stay_days: int | None = None
    neighborhood: str | None = None
    location_text: str | None = None
    address: str | None = None
    contact_email: str | None = None
    contact_method: str | None = None
    listing_type: str | None = None
    furnished: bool | None = None
    flags: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)
    status: Status = Status.NEW
    score: int = 0
    commute_minutes: int | None = None
    commute_bucket: str | None = None
    directions_url: str | None = None
    message: str = ""
    listing_id: str = ""
    raw_source_id: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    auto_sent_at: datetime | None = None
    manually_approved: bool = False

    def add_flag(self, flag: str) -> None:
        if flag in FLAGS:
            self.flags.add(flag)

    def as_sheet_row(self) -> dict[str, Any]:
        return {
            "Score": self.score,
            "Status": self.status.value,
            "Price": self.price or "",
            "Area": self.neighborhood or self.location_text or "",
            "Dates": _date_range(self.available_from, self.available_to),
            "Type": self.listing_type or "",
            "Source": self.source,
            "Link": self.url,
            "Message": self.message,
            "Flags": ", ".join(sorted(self.flags)),
            "listing_id": self.listing_id,
            "commute_minutes": self.commute_minutes or "",
            "commute_bucket": self.commute_bucket or "",
            "contact_method": self.contact_method or "",
            "auto_sent_at": self.auto_sent_at.isoformat() if self.auto_sent_at else "",
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else "",
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else "",
            "raw_source_id": self.raw_source_id or "",
        }


def _date_range(start: date | None, end: date | None) -> str:
    if start and end:
        return f"{start.isoformat()} to {end.isoformat()}"
    if start:
        return f"from {start.isoformat()}"
    if end:
        return f"until {end.isoformat()}"
    return ""

