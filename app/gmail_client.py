from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.models import RawEmail


class GmailClient(Protocol):
    def fetch_messages(self, queries: list[str]) -> list[RawEmail]:
        ...

    def send_email(self, to: str, subject: str, body: str) -> None:
        ...


class MissingGmailCredentials(RuntimeError):
    pass


class FixtureGmailClient:
    def __init__(self, fixture_dir: str | Path):
        self.fixture_dir = Path(fixture_dir)

    def fetch_messages(self, queries: list[str]) -> list[RawEmail]:
        messages: list[RawEmail] = []
        for path in sorted(self.fixture_dir.glob("*.html")):
            messages.append(
                RawEmail(
                    raw_source_id=f"fixture:{path.name}",
                    sender=_sender_for(path.name),
                    subject=path.stem.replace("_", " ").title(),
                    body=path.read_text(encoding="utf-8"),
                    received_at=datetime(2026, 7, 1, 12, 0, 0),
                )
            )
        return messages

    def send_email(self, to: str, subject: str, body: str) -> None:
        raise RuntimeError("FixtureGmailClient cannot send email.")


class RealGmailClient:
    def __init__(self) -> None:
        if not os.getenv("GMAIL_CREDENTIALS_JSON"):
            raise MissingGmailCredentials("Missing Gmail credentials. Set GMAIL_CREDENTIALS_JSON before non-dry-run Gmail actions.")

    def fetch_messages(self, queries: list[str]) -> list[RawEmail]:
        raise NotImplementedError("Wire this thin wrapper to the Gmail API for production use.")

    def send_email(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError("Wire this thin wrapper to the Gmail API for production use.")


def _sender_for(filename: str) -> str:
    if "craigslist" in filename:
        return "alerts@craigslist.org"
    if "streeteasy" in filename:
        return "alerts@streeteasy.com"
    return "newsletter@example.com"

