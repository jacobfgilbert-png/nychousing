from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from app.models import Listing
from app.parsers.generic_email import parse as parse_generic


@dataclass(frozen=True)
class SourceStats:
    fetched_sources: int = 0
    fetched_items: int = 0
    failed_sources: int = 0


def fetch_configured_source_listings(web_sources: dict, fixture_dir: Path | None = None) -> tuple[list[Listing], SourceStats]:
    if not web_sources.get("enabled", True):
        return [], SourceStats()
    listings: list[Listing] = []
    failed = 0
    feeds = web_sources.get("rss_feeds", [])
    for feed in feeds:
        try:
            xml_text = _read_feed(feed["url"], fixture_dir)
            listings.extend(parse_rss_feed(xml_text, source=feed.get("source", _source_from_url(feed["url"]))))
        except Exception as exc:
            failed += 1
            print(f"Source fetch failed for {feed.get('name') or feed.get('url')}: {exc}")
    return listings, SourceStats(fetched_sources=len(feeds), fetched_items=len(listings), failed_sources=failed)


def parse_rss_feed(xml_text: str, source: str = "rss") -> list[Listing]:
    root = ET.fromstring(xml_text)
    listings: list[Listing] = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link")
        description = _text(item, "description")
        text = "\n".join(part for part in [title, description, link] if part)
        parsed = parse_generic(text, source=source, subject=title)
        listing = parsed[0] if parsed else Listing(source=source, title=title, description=_clean(description), url=link)
        listing.source = source
        listing.title = title or listing.title
        listing.description = _clean(description or listing.description)
        listing.url = link or listing.url
        listing.source_listing_id = _listing_id_from_url(listing.url)
        listing.contact_method = listing.contact_method or "listing_page"
        if source == "craigslist":
            listing.furnished = listing.furnished if listing.furnished is not None else _craigslist_furnished_guess(listing)
        listings.append(listing)
    return listings


def _read_feed(url: str, fixture_dir: Path | None = None) -> str:
    if fixture_dir is not None:
        if "://" in url:
            raise FileNotFoundError(f"fixture not found for {url}")
        fixture_path = fixture_dir / url
        return fixture_path.read_text(encoding="utf-8")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
            "Accept": "application/rss+xml,application/xml,text/xml,text/html;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _text(item: ET.Element, tag: str) -> str:
    found = item.find(tag)
    return unescape(found.text or "").strip() if found is not None else ""


def _clean(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _source_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "craigslist" in host:
        return "craigslist"
    if "leasebreak" in host:
        return "leasebreak"
    return host or "web"


def _listing_id_from_url(url: str) -> str | None:
    if not url:
        return None
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1]
    return slug.split(".")[0] if slug else None


def _craigslist_furnished_guess(listing: Listing) -> bool | None:
    text = f"{listing.title} {listing.description}".lower()
    if "unfurnished" in text:
        return False
    if "furnished" in text:
        return True
    return None
