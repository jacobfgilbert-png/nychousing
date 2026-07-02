from __future__ import annotations

from datetime import date, timedelta

from app.config import AppConfig
from app.models import Listing


def score_listing(listing: Listing, config: AppConfig) -> Listing:
    search = config.section("search")
    move_in = date.fromisoformat(search["move_in_date"])
    flex = int(search["move_in_flex_days"])
    score = 0
    if listing.price is not None and listing.price <= int(search["max_monthly_price"]):
        score += 20
        listing.reasons.append("Score +20: price within budget.")
        if listing.price <= 2000:
            score += 8
            listing.reasons.append("Score +8: price at or below $2,000.")
    elif listing.price is None:
        score -= 15
        listing.reasons.append("Score -15: missing price.")

    if listing.furnished is True:
        score += 25
        listing.reasons.append("Score +25: furnished confirmed.")
    if listing.listing_type == "whole_place":
        score += 18
        listing.reasons.append("Score +18: whole place.")
    elif listing.listing_type == "private_room":
        score += 10
        listing.reasons.append("Score +10: private room.")

    if listing.available_from and (move_in - timedelta(days=flex)) <= listing.available_from <= (move_in + timedelta(days=flex)):
        score += 20
        listing.reasons.append("Score +20: move-in date matches flex window.")
    elif listing.available_from is None:
        score -= 10
        listing.reasons.append("Score -10: missing dates.")

    if _stay_length_ok(listing, int(search["min_stay_days"]), int(search["max_stay_days"])):
        score += 15
        listing.reasons.append("Score +15: stay length can fit 1-3 months.")

    if listing.commute_bucket == "excellent":
        score += 25
        listing.reasons.append("Score +25: excellent commute.")
    elif listing.commute_bucket == "acceptable":
        score += 15
        listing.reasons.append("Score +15: acceptable commute.")

    if is_favorite_neighborhood(listing, config):
        score += 10
        listing.reasons.append("Score +10: favorite neighborhood.")

    if "scam_risk" in listing.flags:
        score -= 30
        listing.reasons.append("Score -30: scam or risk flag.")

    score = max(0, min(100, score))
    if listing.commute_bucket == "weak":
        score = min(score, 70)
        listing.reasons.append("Score capped at 70: weak commute.")
    if "scam_risk" in listing.flags and not listing.manually_approved:
        score = min(score, 60)
        listing.reasons.append("Score capped at 60: scam risk requires manual approval.")
    listing.score = score
    return listing


def is_favorite_neighborhood(listing: Listing, config: AppConfig) -> bool:
    text = " ".join(filter(None, [listing.neighborhood, listing.location_text, listing.title, listing.description])).lower()
    return any(name.lower() in text for name in config.section("location")["favorite_neighborhoods"])


def _stay_length_ok(listing: Listing, min_days: int, max_days: int) -> bool:
    if listing.min_stay_days is None and listing.max_stay_days is None:
        return listing.available_from is not None
    if listing.min_stay_days is not None and listing.min_stay_days > max_days:
        return False
    if listing.max_stay_days is not None and listing.max_stay_days < min_days:
        return False
    return True

