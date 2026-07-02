from datetime import date

from app.config import load_config
from app.draft_message import build_message
from app.models import Listing


def cfg():
    config = load_config("missing.yaml", root=".")
    config.values["messaging"]["phone_number"] = "555-1212"
    return config


def test_message_with_clear_dates():
    message = build_message(Listing(available_from=date(2026, 10, 1)), cfg())
    assert "I saw the dates" in message
    assert "555-1212" in message


def test_message_without_clear_dates():
    message = build_message(Listing(), cfg())
    assert "around Oct 1" in message
    assert "roughly 1-3 months" in message

