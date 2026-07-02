from app.dedupe import is_duplicate, likely_same_title
from app.models import Listing


def test_exact_url_duplicate():
    original = Listing(url="https://example.com/a", title="A")
    candidate = Listing(url="https://example.com/a", title="B")
    assert is_duplicate(candidate, [original]) is original


def test_fuzzy_title_helper():
    assert likely_same_title("Furnished Astoria Studio", "furnished astoria studio!")

