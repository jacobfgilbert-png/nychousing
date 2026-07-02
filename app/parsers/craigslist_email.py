from __future__ import annotations

from app.models import Listing
from app.parsers.generic_email import parse as parse_generic


def parse(body: str, subject: str = "") -> list[Listing]:
    listings = parse_generic(body, source="craigslist", subject=subject)
    for listing in listings:
        if listing.url and "craigslist" in listing.url:
            listing.source_listing_id = listing.url.rstrip("/").split("/")[-1].split(".")[0]
    return listings

