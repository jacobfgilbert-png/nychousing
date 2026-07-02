from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus

from app.commute_table import CommuteEntry, load_commute_table
from app.config import AppConfig, resolve_path
from app.models import Listing, Status


OUTSIDE_NYC = {"new jersey", "jersey city", "hoboken", "philadelphia", "boston", "connecticut"}


def apply_location(listing: Listing, config: AppConfig) -> Listing:
    text = " ".join(filter(None, [listing.neighborhood, listing.location_text, listing.description, listing.title]))
    if _clearly_outside_nyc(text):
        listing.status = Status.REJECTED
        listing.reasons.append("Rejected: location is clearly outside NYC.")
        return listing

    aliases = load_aliases(resolve_path(config, config.section("location")["aliases_path"]))
    commute = load_commute_table(resolve_path(config, config.section("location")["commute_table_path"]))
    match_name = match_neighborhood(text, aliases, commute)
    if not match_name:
        listing.add_flag("check_location")
        listing.reasons.append("Location unclear; kept for manual location check if otherwise promising.")
        return listing

    entry = commute[match_name.lower()]
    listing.neighborhood = entry.nta_name
    listing.commute_minutes = entry.commute_minutes
    listing.commute_bucket = entry.commute_bucket
    listing.reasons.append(f"Matched location to {entry.nta_name}: {entry.commute_minutes} minutes, {entry.commute_bucket}.")
    if entry.commute_bucket == "weak":
        listing.add_flag("check_commute")
    if listing.address:
        listing.directions_url = directions_url(listing.address, config.section("location")["commute_target"])
    return listing


def load_aliases(path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    current: str | None = None
    if not path.exists():
        return aliases
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not raw.startswith(" ") and line.endswith(":"):
            current = line[:-1]
            aliases[current.lower()] = current
        elif line.startswith("- ") and current:
            aliases[line[2:].strip().lower()] = current
    return aliases


def match_neighborhood(text: str, aliases: dict[str, str], commute: dict[str, CommuteEntry]) -> str | None:
    low = text.lower()
    for alias, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", low) and canonical.lower() in commute:
            return canonical
    for canonical in commute:
        if re.search(rf"\b{re.escape(canonical)}\b", low):
            return commute[canonical].nta_name
    return None


def directions_url(origin: str, destination: str) -> str:
    return f"https://www.google.com/maps/dir/?api=1&origin={quote_plus(origin)}&destination={quote_plus(destination)}&travelmode=transit"


def _clearly_outside_nyc(text: str) -> bool:
    low = text.lower()
    return any(place in low for place in OUTSIDE_NYC)
