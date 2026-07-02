from pathlib import Path

from app.parsers import parse_craigslist, parse_generic, parse_streeteasy


FIXTURES = Path(__file__).parent / "fixtures"


def test_craigslist_parser_extracts_core_fields():
    listings = parse_craigslist((FIXTURES / "craigslist_email.html").read_text(), "Craigslist alert")
    listing = listings[0]
    assert listing.source == "craigslist"
    assert listing.price == 2100
    assert listing.furnished is True
    assert listing.listing_type == "whole_place"
    assert listing.neighborhood == "Astoria"
    assert listing.contact_email == "owner@example.com"
    assert "craigslist" in listing.url


def test_streeteasy_parser_uses_listing_page_contact():
    listing = parse_streeteasy((FIXTURES / "streeteasy_email.html").read_text())[0]
    assert listing.source == "streeteasy"
    assert listing.price == 2450
    assert listing.neighborhood == "Forest Hills"
    assert listing.contact_method == "listing_page"


def test_generic_parser_keeps_newsletter_listing():
    listing = parse_generic((FIXTURES / "generic_newsletter.html").read_text())[0]
    assert listing.price == 1700
    assert listing.neighborhood == "Bushwick"
    assert listing.listing_type == "private_room"

