from __future__ import annotations

import re
from datetime import datetime, time

from app.config import AppConfig
from app.models import Listing, Status

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)
MAJOR_FLAGS = {"check_price", "check_dates", "check_location", "check_commute", "check_furnished", "scam_risk"}


def prepare_outbox(listing: Listing, config: AppConfig, now: datetime | None = None) -> Listing:
    if listing.status == Status.REJECTED:
        return listing
    if can_auto_send(listing, config, now):
        listing.status = Status.NEW
        listing.reasons.append("Eligible for auto-send.")
    else:
        if not listing.contact_email:
            listing.add_flag("missing_contact")
        listing.status = Status.NEEDS_MANUAL_SEND
        listing.reasons.append("Needs manual send or review.")
    return listing


def can_auto_send(listing: Listing, config: AppConfig, now: datetime | None = None, sent_this_hour: int = 0) -> bool:
    msg = config.section("messaging")
    if msg.get("mode") != "auto_send_clean_email_only":
        return False
    if listing.score < int(msg["auto_send_min_score"]):
        return False
    if listing.flags & MAJOR_FLAGS:
        return False
    if listing.auto_sent_at:
        return False
    if listing.contact_method != "email" or not listing.contact_email or not EMAIL_RE.match(listing.contact_email):
        return False
    if sent_this_hour >= int(msg["max_auto_sends_per_hour"]):
        return False
    return not in_quiet_hours(now or datetime.now(), msg["quiet_hours_start"], msg["quiet_hours_end"])


def mark_sent(listing: Listing, sent_at: datetime | None = None) -> Listing:
    listing.status = Status.AUTO_SENT
    listing.auto_sent_at = sent_at or datetime.now()
    listing.reasons.append("Auto-sent message logged.")
    return listing


def in_quiet_hours(now: datetime, start: str, end: str) -> bool:
    start_time = _parse_time(start)
    end_time = _parse_time(end)
    current = now.time()
    if start_time < end_time:
        return start_time <= current < end_time
    return current >= start_time or current < end_time


def _parse_time(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))

