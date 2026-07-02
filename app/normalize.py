from __future__ import annotations

import re
from hashlib import sha1

from app.models import Listing


def normalize_listing(listing: Listing) -> Listing:
    listing.title = _spaces(listing.title)
    listing.description = _spaces(listing.description)
    listing.url = listing.url.strip()
    if listing.contact_email:
        listing.contact_email = listing.contact_email.lower()
    if listing.neighborhood:
        listing.neighborhood = _title_case(listing.neighborhood)
    if listing.location_text:
        listing.location_text = _spaces(listing.location_text)
    listing.listing_id = stable_listing_id(listing)
    return listing


def stable_listing_id(listing: Listing) -> str:
    key = listing.url or "|".join(
        [
            listing.source,
            listing.source_listing_id or "",
            listing.title.lower(),
            str(listing.price or ""),
            (listing.neighborhood or listing.location_text or "").lower(),
        ]
    )
    return sha1(key.encode("utf-8")).hexdigest()[:16]


def _spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in _spaces(value).split(" "))

