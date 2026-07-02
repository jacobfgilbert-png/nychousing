from __future__ import annotations

from app.models import Listing
from app.parsers.generic_email import parse as parse_generic


def parse(text: str, subject: str = "Manual import") -> list[Listing]:
    listings = parse_generic(text, source="manual", subject=subject)
    for listing in listings:
        if not listing.contact_method and listing.url:
            listing.contact_method = "listing_page"
    return listings

