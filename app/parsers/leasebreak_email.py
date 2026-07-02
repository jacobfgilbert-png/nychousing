from __future__ import annotations

from app.models import Listing
from app.parsers.generic_email import parse as parse_generic


def parse(body: str, subject: str = "") -> list[Listing]:
    return parse_generic(body, source="leasebreak", subject=subject)

