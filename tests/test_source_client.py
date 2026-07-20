from pathlib import Path

from app.source_client import fetch_configured_source_listings, parse_rss_feed


def test_parse_rss_feed_extracts_listings():
    xml_text = (Path(__file__).parent / "fixtures" / "sources" / "craigslist_sample.rss").read_text(encoding="utf-8")
    listings = parse_rss_feed(xml_text, source="craigslist")

    assert len(listings) == 2
    assert listings[0].source == "craigslist"
    assert listings[0].price == 2100
    assert listings[0].neighborhood == "Astoria"
    assert listings[0].contact_method == "listing_page"
    assert listings[0].source_listing_id == "999111"


def test_fetch_configured_source_listings_uses_fixture_dir():
    fixture_dir = Path(__file__).parent / "fixtures" / "sources"
    listings, stats = fetch_configured_source_listings(
        {"enabled": True, "rss_feeds": [{"name": "sample", "source": "craigslist", "url": "craigslist_sample.rss"}]},
        fixture_dir=fixture_dir,
    )

    assert len(listings) == 2
    assert stats.fetched_sources == 1
    assert stats.fetched_items == 2
    assert stats.failed_sources == 0
