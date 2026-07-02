from __future__ import annotations

from datetime import date, timedelta

from app.config import AppConfig
from app.models import Listing, Status


def apply_filters(listing: Listing, config: AppConfig) -> Listing:
    search = config.section("search")
    max_price = int(search["max_monthly_price"])
    if listing.price is not None and listing.price > max_price:
        return _reject(listing, f"Rejected: price ${listing.price} exceeds ${max_price}.")
    if listing.price is None:
        listing.add_flag("check_price")
        listing.reasons.append("Price missing or unclear.")

    if search["furnished_required"] and listing.furnished is False:
        return _reject(listing, "Rejected: listing is clearly unfurnished.")
    if listing.furnished is None:
        listing.add_flag("check_furnished")
        listing.reasons.append("Furnished status missing or unclear.")

    if not dates_can_work(listing, date.fromisoformat(search["move_in_date"]), int(search["move_in_flex_days"])):
        return _reject(listing, "Rejected: dates clearly cannot work for Oct 1 move-in.")
    if listing.available_from is None:
        listing.add_flag("check_dates")
        listing.reasons.append("Dates missing or unclear.")

    if listing.commute_bucket == "reject":
        return _reject(listing, "Rejected: commute is over 75 minutes.")

    if _too_weak_when_unclear(listing):
        return _reject(listing, "Rejected: too many critical fields are unclear.")
    return listing


def dates_can_work(listing: Listing, move_in: date, flex_days: int) -> bool:
    if listing.available_from is None:
        return True
    earliest = move_in - timedelta(days=flex_days)
    latest = move_in + timedelta(days=flex_days)
    return earliest <= listing.available_from <= latest


def _too_weak_when_unclear(listing: Listing) -> bool:
    critical = {"check_price", "check_dates", "check_location", "check_furnished"}
    return len(listing.flags & critical) >= 3 and listing.contact_method is None


def _reject(listing: Listing, reason: str) -> Listing:
    listing.status = Status.REJECTED
    listing.reasons.append(reason)
    return listing

