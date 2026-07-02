from __future__ import annotations

import re
from datetime import date
from html import unescape

from app.models import Listing


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.I)
PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]{2,5})(?:\s*/?\s*(?:month|mo))?", re.I)
DATE_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})|(?:oct(?:ober)?\.?\s+)(\d{1,2})", re.I)
NEIGHBORHOODS = [
    "Astoria",
    "Inwood",
    "Jackson Heights",
    "Forest Hills",
    "Williamsburg",
    "Bushwick",
    "Harlem",
    "Queens",
    "Brooklyn",
    "Manhattan",
    "Bronx",
    "Staten Island",
]


def parse(body: str, source: str = "generic", subject: str = "") -> list[Listing]:
    text = clean_text(body)
    chunks = _split_chunks(text)
    listings = [_parse_chunk(chunk, source, subject) for chunk in chunks]
    return [listing for listing in listings if listing.title or listing.url or listing.price]


def clean_text(body: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    text = re.sub(r"</p>|</div>|</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _split_chunks(text: str) -> list[str]:
    if len(re.findall(r"\bListing:", text, flags=re.I)) > 1:
        return [part.strip() for part in re.split(r"(?=Listing:)", text) if part.strip()]
    return [text]


def _parse_chunk(chunk: str, source: str, subject: str) -> Listing:
    url = _first(URL_RE, chunk)
    email = _first(EMAIL_RE, chunk)
    price = _price(chunk)
    start = _date(chunk)
    furnished = _furnished(chunk)
    listing_type = _listing_type(chunk)
    neighborhood = _neighborhood(chunk)
    title = _title(chunk, subject)
    contact_method = "email" if email else ("listing_page" if url else None)
    return Listing(
        source=source,
        title=title,
        description=chunk[:1000],
        url=url or "",
        price=price,
        available_from=start,
        neighborhood=neighborhood,
        location_text=neighborhood,
        contact_email=email,
        contact_method=contact_method,
        listing_type=listing_type,
        furnished=furnished,
    )


def _first(regex: re.Pattern[str], text: str) -> str | None:
    match = regex.search(text)
    return match.group(0).rstrip(").,") if match else None


def _price(text: str) -> int | None:
    match = PRICE_RE.search(text)
    return int(match.group(1).replace(",", "")) if match else None


def _date(text: str) -> date | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    if match.group(1):
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return date(2026, 10, int(match.group(4)))


def _furnished(text: str) -> bool | None:
    low = text.lower()
    if "unfurnished" in low:
        return False
    if "furnished" in low:
        return True
    return None


def _listing_type(text: str) -> str | None:
    low = text.lower()
    if any(term in low for term in ["whole place", "entire apartment", "studio", "1br", "one bedroom"]):
        return "whole_place"
    if any(term in low for term in ["room", "private room", "share"]):
        return "private_room"
    return None


def _neighborhood(text: str) -> str | None:
    low = text.lower()
    for name in NEIGHBORHOODS:
        if name.lower() in low:
            return name
    return None


def _title(text: str, subject: str) -> str:
    for line in text.splitlines():
        line = line.strip(" -")
        if line and len(line) <= 120:
            return line
    return subject[:120]
