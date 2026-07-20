from datetime import datetime

from app.main import is_housing_email
from app.models import RawEmail


def test_skips_google_account_notification():
    email = RawEmail(
        raw_source_id="google-1",
        sender="Google <no-reply@accounts.google.com>",
        subject="Security alert",
        body="Review this at https://myaccount.google.com/notifications",
        received_at=datetime(2026, 7, 20, 8, 0, 0),
    )
    assert not is_housing_email(email)


def test_keeps_generic_housing_email():
    email = RawEmail(
        raw_source_id="housing-1",
        sender="newsletter@example.com",
        subject="Furnished room available in Astoria",
        body="Short term rental / furnished room available Oct 1 for $1800.",
        received_at=datetime(2026, 7, 20, 8, 0, 0),
    )
    assert is_housing_email(email)

