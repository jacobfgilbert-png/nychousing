from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from email.mime.text import MIMEText
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
        credentials_json = os.getenv("GMAIL_CREDENTIALS_JSON")
        if not credentials_json:
            raise MissingGmailCredentials("Missing Gmail credentials. Set GMAIL_CREDENTIALS_JSON before non-dry-run Gmail actions.")
        self.service = _build_gmail_service(credentials_json)

    def fetch_messages(self, queries: list[str]) -> list[RawEmail]:
        seen: set[str] = set()
        messages: list[RawEmail] = []
        for query in queries:
            response = self.service.users().messages().list(userId="me", q=query, maxResults=25).execute()
            for item in response.get("messages", []):
                message_id = item["id"]
                if message_id in seen:
                    continue
                seen.add(message_id)
                payload = self.service.users().messages().get(userId="me", id=message_id, format="full").execute()
                messages.append(_raw_email_from_gmail(payload))
        return messages

    def send_email(self, to: str, subject: str, body: str) -> None:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        self.service.users().messages().send(userId="me", body={"raw": encoded}).execute()


def _sender_for(filename: str) -> str:
    if "craigslist" in filename:
        return "alerts@craigslist.org"
    if "streeteasy" in filename:
        return "alerts@streeteasy.com"
    return "newsletter@example.com"


def _build_gmail_service(credentials_json: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    info = json.loads(credentials_json)
    scopes = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
    credentials = Credentials.from_authorized_user_info(info, scopes=scopes)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _raw_email_from_gmail(payload: dict) -> RawEmail:
    headers = {header["name"].lower(): header["value"] for header in payload.get("payload", {}).get("headers", [])}
    date_value = headers.get("date")
    received_at = datetime.now()
    if date_value:
        try:
            from email.utils import parsedate_to_datetime

            received_at = parsedate_to_datetime(date_value)
        except (TypeError, ValueError):
            pass
    return RawEmail(
        raw_source_id=payload["id"],
        sender=headers.get("from", ""),
        subject=headers.get("subject", ""),
        body=_decode_parts(payload.get("payload", {})),
        received_at=received_at,
    )


def _decode_parts(payload: dict) -> str:
    data = payload.get("body", {}).get("data")
    if data:
        return _decode_data(data)
    parts = payload.get("parts", [])
    html_chunks: list[str] = []
    text_chunks: list[str] = []
    for part in parts:
        mime_type = part.get("mimeType", "")
        body = _decode_parts(part)
        if not body:
            continue
        if mime_type == "text/html":
            html_chunks.append(body)
        else:
            text_chunks.append(body)
    return "\n".join(html_chunks or text_chunks)


def _decode_data(data: str) -> str:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii")).decode("utf-8", errors="replace")
