from __future__ import annotations

from app.models import Listing


def digest(listings: list[Listing], min_score: int) -> str:
    selected = [listing for listing in listings if listing.score >= min_score]
    lines = [f"{listing.score}: {listing.title} ({listing.url})" for listing in selected]
    return "\n".join(lines)
