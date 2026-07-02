from datetime import date

from app.config import load_config
from app.filters import apply_filters
from app.models import Listing, Status


def cfg():
    return load_config("missing.yaml", root=".")


def test_rejects_clear_over_budget():
    listing = apply_filters(Listing(price=2600, furnished=True, available_from=date(2026, 10, 1)), cfg())
    assert listing.status == Status.REJECTED
    assert "exceeds" in listing.reasons[-1]


def test_missing_price_is_flagged_not_rejected():
    listing = apply_filters(Listing(furnished=True, available_from=date(2026, 10, 1), contact_method="listing_page"), cfg())
    assert listing.status == Status.NEW
    assert "check_price" in listing.flags


def test_rejects_unfurnished():
    listing = apply_filters(Listing(price=2000, furnished=False, available_from=date(2026, 10, 1)), cfg())
    assert listing.status == Status.REJECTED


def test_rejects_incompatible_dates():
    listing = apply_filters(Listing(price=2000, furnished=True, available_from=date(2026, 12, 1)), cfg())
    assert listing.status == Status.REJECTED

