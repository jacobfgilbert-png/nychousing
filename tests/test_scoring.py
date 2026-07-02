from datetime import date

from app.config import load_config
from app.models import Listing
from app.scoring import score_listing


def cfg():
    return load_config("missing.yaml", root=".")


def test_favorite_neighborhood_bonus_and_clamp():
    listing = Listing(
        title="Astoria furnished apartment",
        price=1800,
        furnished=True,
        listing_type="whole_place",
        available_from=date(2026, 10, 1),
        neighborhood="Astoria",
        commute_bucket="excellent",
    )
    scored = score_listing(listing, cfg())
    assert scored.score == 100
    assert any("favorite" in reason for reason in scored.reasons)


def test_weak_commute_caps_score_at_70():
    listing = Listing(
        title="Bushwick furnished whole place",
        price=1800,
        furnished=True,
        listing_type="whole_place",
        available_from=date(2026, 10, 1),
        neighborhood="Bushwick",
        commute_bucket="weak",
    )
    assert score_listing(listing, cfg()).score == 70


def test_scam_risk_caps_score_at_60():
    listing = Listing(price=1800, furnished=True, listing_type="whole_place", available_from=date(2026, 10, 1), commute_bucket="excellent")
    listing.flags.add("scam_risk")
    assert score_listing(listing, cfg()).score == 60

