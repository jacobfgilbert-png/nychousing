from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.models import Listing


@dataclass(frozen=True)
class YerrStats:
    fetched_pages: int = 0
    fetched_items: int = 0
    failed_pages: int = 0
    total_available: int = 0


def fetch_yerr_listings(config: dict) -> tuple[list[Listing], YerrStats]:
    if not config.get("enabled", True):
        return [], YerrStats()
    base_url = str(config.get("base_url", "https://yerr.org/api/listings"))
    limit = int(config.get("limit", 100))
    max_pages = int(config.get("max_pages", 10))
    params = _query_params(config, limit)
    listings: list[Listing] = []
    fetched_pages = 0
    failed_pages = 0
    total_available = 0
    offset = 0
    for _ in range(max_pages):
        page_params = [*params, ("offset", str(offset))]
        url = f"{base_url}?{urllib.parse.urlencode(page_params)}"
        try:
            data = _read_json(url)
        except Exception as exc:
            failed_pages += 1
            print(f"YERR fetch failed for offset {offset}: {exc}")
            break
        page_listings, total_available, has_more = parse_yerr_response(data)
        listings.extend(page_listings)
        fetched_pages += 1
        if not has_more or not page_listings:
            break
        offset += len(page_listings)
    return listings, YerrStats(
        fetched_pages=fetched_pages,
        fetched_items=len(listings),
        failed_pages=failed_pages,
        total_available=total_available,
    )


def parse_yerr_response(data: dict[str, Any]) -> tuple[list[Listing], int, bool]:
    items = data.get("listings", [])
    meta = data.get("meta", {})
    listings = [_listing_from_yerr(item) for item in items if isinstance(item, dict)]
    return listings, int(meta.get("total") or len(listings)), bool(meta.get("has_more"))


def _query_params(config: dict, limit: int) -> list[tuple[str, str]]:
    params = [("limit", str(limit))]
    if config.get("max_price"):
        params.append(("max_price", str(config["max_price"])))
    for value in config.get("listing_types", ["sublet", "lease_break"]):
        params.append(("listing_type", str(value)))
    for value in config.get("source_platforms", ["reddit", "facebook", "craigslist", "listingproject"]):
        params.append(("source_platform", str(value)))
    for value in config.get("boroughs", []):
        params.append(("borough", str(value)))
    for value in config.get("areas", []):
        params.append(("area", str(value)))
    return params


def _read_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _listing_from_yerr(item: dict[str, Any]) -> Listing:
    platform = str(item.get("sourcePlatform") or "yerr")
    source = f"yerr:{platform}"
    url = str(item.get("sourceUrl") or "")
    neighborhood = _clean_location(item.get("neighborhood") or item.get("borough"))
    listing_type = "private_room" if item.get("isRoomOnly") else "whole_place"
    title = str(item.get("title") or "")
    amenities = item.get("amenities") if isinstance(item.get("amenities"), list) else []
    description = " | ".join(str(value) for value in [title, *amenities] if value)
    return Listing(
        source=source,
        title=title[:240],
        description=description[:3000],
        url=url,
        source_listing_id=str(item.get("sourceId") or item.get("id") or url),
        price=_parse_price(item.get("price")),
        available_from=_parse_date(item.get("availableAt")),
        neighborhood=neighborhood,
        location_text=neighborhood,
        contact_method="listing_page" if url else None,
        listing_type=listing_type,
        furnished=item.get("isFurnished") if isinstance(item.get("isFurnished"), bool) else None,
    )


def _parse_price(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _clean_location(value: Any) -> str | None:
    if not value:
        return None
    return str(value).replace("_", " ").strip().title()
