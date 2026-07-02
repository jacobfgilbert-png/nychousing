from __future__ import annotations

from app.config import AppConfig
from app.models import Listing


DATES_CLEAR_TEMPLATE = (
    "Hi, I'm interested in your furnished sublet. I saw the dates in the listing and they look like they could work for me. "
    "I'm a WFH product manager, though I usually work out of the house a lot. I came to NYC to visit friends, ended up really "
    "enjoying it, and I'm testing out moving here longer-term. I'm clean, quiet, respectful, and flexible within reason. "
    "Is the place still available? You can also text me at {{phone_number}}. Thanks."
)

DATES_UNCLEAR_TEMPLATE = (
    "Hi, I'm interested in your furnished sublet. I'm looking to move in around Oct 1 for roughly 1-3 months, with some flexibility. "
    "I'm a WFH product manager, though I usually work out of the house a lot. I came to NYC to visit friends, ended up really enjoying "
    "it, and I'm testing out moving here longer-term. I'm clean, quiet, respectful, and flexible within reason. Is the place still "
    "available? You can also text me at {{phone_number}}. Thanks."
)


def build_message(listing: Listing, config: AppConfig) -> str:
    template = DATES_CLEAR_TEMPLATE if listing.available_from else DATES_UNCLEAR_TEMPLATE
    return template.replace("{{phone_number}}", config.section("messaging").get("phone_number", ""))

