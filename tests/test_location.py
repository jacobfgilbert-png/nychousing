from app.config import load_config
from app.location import apply_location
from app.models import Listing, Status


def cfg():
    return load_config("missing.yaml", root=".")


def test_matches_alias_to_commute_table():
    listing = apply_location(Listing(description="Great furnished place in Ditmars"), cfg())
    assert listing.neighborhood == "Astoria"
    assert listing.commute_bucket == "excellent"


def test_rejects_commute_bucket_reject_after_filtering():
    listing = apply_location(Listing(description="Furnished place in Far Rockaway"), cfg())
    assert listing.commute_bucket == "reject"


def test_outside_nyc_rejected():
    listing = apply_location(Listing(description="Furnished room in Hoboken"), cfg())
    assert listing.status == Status.REJECTED


def test_missing_location_flagged():
    listing = apply_location(Listing(description="Nice furnished place"), cfg())
    assert "check_location" in listing.flags

