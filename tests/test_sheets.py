from app.models import Listing, Status
from app.sheets_client import _dashboard_row_is_actionable, _listing_is_actionable


def test_rejected_listing_is_not_dashboard_actionable():
    assert not _listing_is_actionable(Listing(status=Status.REJECTED, score=0, source="generic"))


def test_google_account_row_is_not_dashboard_actionable():
    row = {"Score": "0", "Status": "needs_manual_send", "Source": "generic", "Link": "https://myaccount.google.com/notifications"}
    assert not _dashboard_row_is_actionable(row)


def test_real_scored_row_is_dashboard_actionable():
    row = {"Score": "82", "Status": "needs_manual_send", "Source": "generic", "Link": "https://example.com/sublet"}
    assert _dashboard_row_is_actionable(row)
