from __future__ import annotations

from app.models import Listing
from app.parsers.generic_email import parse as parse_generic


def parse(body: str, subject: str = "") -> list[Listing]:
    listings = parse_generic(body, source="streeteasy", subject=subject)
    for listing in listings:
        listing.contact_method = listing.contact_method or "listing_page"
    return listings

