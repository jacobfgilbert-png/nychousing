from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.models import Listing
from app.parsers.generic_email import parse as parse_generic
from app.source_client import parse_rss_feed


@dataclass(frozen=True)
class BulkImportStats:
    scanned_files: int = 0
    imported_items: int = 0
    failed_files: int = 0


SUPPORTED_SUFFIXES = {".csv", ".tsv", ".json", ".jsonl", ".rss", ".xml", ".html", ".htm", ".txt", ".md"}


def import_configured_bulk_listings(bulk_config: dict, root: Path) -> tuple[list[Listing], BulkImportStats]:
    if not bulk_config.get("enabled", True):
        return [], BulkImportStats()
    import_dir = Path(bulk_config.get("import_dir", "data/imports"))
    if not import_dir.is_absolute():
        import_dir = root / import_dir
    if not import_dir.exists():
        return [], BulkImportStats()
    return import_bulk_dir(import_dir)


def import_bulk_dir(import_dir: Path) -> tuple[list[Listing], BulkImportStats]:
    listings: list[Listing] = []
    scanned = 0
    failed = 0
    for path in sorted(import_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        scanned += 1
        try:
            listings.extend(import_bulk_file(path))
        except Exception as exc:
            failed += 1
            print(f"Bulk import failed for {path}: {exc}")
    return listings, BulkImportStats(scanned_files=scanned, imported_items=len(listings), failed_files=failed)


def import_bulk_file(path: Path) -> list[Listing]:
    suffix = path.suffix.lower()
    if suffix in {".rss", ".xml"}:
        return parse_rss_feed(path.read_text(encoding="utf-8"), source=_source_from_path(path))
    if suffix in {".csv", ".tsv"}:
        return _parse_delimited(path, delimiter="\t" if suffix == ".tsv" else ",")
    if suffix == ".json":
        return _parse_json(path)
    if suffix == ".jsonl":
        return _parse_jsonl(path)
    text = path.read_text(encoding="utf-8")
    return parse_generic(text, source=_source_from_path(path), subject=path.stem)


def _parse_delimited(path: Path, delimiter: str) -> list[Listing]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle, delimiter=delimiter)
        return [_listing_from_mapping(row, source=_source_from_path(path)) for row in rows]


def _parse_json(path: Path) -> list[Listing]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        items = data.get("listings") or data.get("results") or data.get("items") or [data]
    else:
        items = data
    return [_listing_from_mapping(item, source=_source_from_path(path)) for item in items if isinstance(item, dict)]


def _parse_jsonl(path: Path) -> list[Listing]:
    listings: list[Listing] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            listings.append(_listing_from_mapping(item, source=_source_from_path(path)))
    return listings


def _listing_from_mapping(row: dict[str, Any], source: str) -> Listing:
    normalized = {_clean_key(key): value for key, value in row.items()}
    title = _first_value(normalized, ["title", "name", "headline", "subject"])
    description = _first_value(normalized, ["description", "body", "text", "summary", "details"])
    url = _first_value(normalized, ["url", "link", "listing_url", "href"])
    location = _first_value(normalized, ["neighborhood", "area", "location", "borough"])
    contact_email = _first_value(normalized, ["contact_email", "email", "reply_email"])
    price = _parse_int(_first_value(normalized, ["price", "rent", "monthly_price", "amount"]))
    furnished = _parse_bool(_first_value(normalized, ["furnished", "is_furnished"]))
    source_listing_id = _first_value(normalized, ["id", "listing_id", "source_listing_id", "post_id"])
    listing_type = _first_value(normalized, ["type", "listing_type", "housing_type"])
    contact_method = "email" if contact_email else ("listing_page" if url else None)
    listing = Listing(
        source=source,
        title=str(title or "")[:240],
        description=str(description or "")[:3000],
        url=str(url or ""),
        source_listing_id=str(source_listing_id) if source_listing_id else None,
        price=price,
        neighborhood=str(location) if location else None,
        location_text=str(location) if location else None,
        contact_email=str(contact_email) if contact_email else None,
        contact_method=contact_method,
        listing_type=str(listing_type) if listing_type else None,
        furnished=furnished,
    )
    if not any([listing.title, listing.description, listing.url, listing.price]):
        listing.description = "Empty imported row"
    return listing


def _clean_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def _first_value(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def _parse_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "furnished"}:
        return True
    if text in {"false", "no", "n", "0", "unfurnished"}:
        return False
    return None


def _source_from_path(path: Path) -> str:
    stem = path.stem.lower()
    for source in ["craigslist", "streeteasy", "leasebreak", "listingsproject", "facebook"]:
        if source in stem:
            return source
    return "bulk_import"
