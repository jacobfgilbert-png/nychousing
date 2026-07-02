from datetime import datetime

from app.config import load_config
from app.models import Listing, Status
from app.outbox import can_auto_send, prepare_outbox


def cfg():
    return load_config("missing.yaml", root=".")


def test_clean_direct_email_can_auto_send():
    listing = Listing(score=85, contact_method="email", contact_email="person@example.com")
    assert can_auto_send(listing, cfg(), datetime(2026, 7, 1, 12, 0))


def test_non_email_contact_needs_manual_send():
    listing = prepare_outbox(Listing(score=95, contact_method="listing_page"), cfg(), datetime(2026, 7, 1, 12, 0))
    assert listing.status == Status.NEEDS_MANUAL_SEND
    assert "missing_contact" in listing.flags


def test_quiet_hours_blocks_auto_send():
    listing = Listing(score=85, contact_method="email", contact_email="person@example.com")
    assert not can_auto_send(listing, cfg(), datetime(2026, 7, 1, 23, 0))

