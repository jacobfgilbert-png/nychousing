from __future__ import annotations

import re
from hashlib import sha1
from difflib import SequenceMatcher

from app.models import Listing


def is_duplicate(candidate: Listing, existing: list[Listing]) -> Listing | None:
    for listing in existing:
        if candidate.url and listing.url and candidate.url == listing.url:
            return listing
        if candidate.source_listing_id and candidate.source_listing_id == listing.source_listing_id:
            return listing
        if fuzzy_key(candidate) == fuzzy_key(listing):
            return listing
        if description_hash(candidate.description) == description_hash(listing.description):
            return listing
    return None


def fuzzy_key(listing: Listing) -> str:
    title = re.sub(r"[^a-z0-9]+", " ", listing.title.lower()).strip()
    location = (listing.neighborhood or listing.location_text or "").lower()
    return f"{title[:60]}|{listing.price or ''}|{location}"


def likely_same_title(left: str, right: str) -> bool:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio() >= 0.88


def description_hash(description: str) -> str:
    normalized = re.sub(r"\s+", " ", description.lower()).strip()[:500]
    return sha1(normalized.encode("utf-8")).hexdigest() if normalized else ""
