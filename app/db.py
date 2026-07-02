from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.models import Listing, RawEmail, Status


def connect(path: str | Path = "sublets.sqlite3") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists raw_emails (
            raw_source_id text primary key,
            sender text not null,
            subject text not null,
            body text not null,
            received_at text not null
        );
        create table if not exists listings (
            listing_id text primary key,
            payload text not null,
            status text not null,
            score integer not null,
            first_seen_at text not null,
            last_seen_at text not null
        );
        create table if not exists outbox (
            listing_id text primary key,
            message text not null,
            sent_at text
        );
        """
    )
    conn.commit()


def save_raw_email(conn: sqlite3.Connection, email: RawEmail) -> bool:
    cur = conn.execute(
        "insert or ignore into raw_emails(raw_source_id, sender, subject, body, received_at) values (?, ?, ?, ?, ?)",
        (email.raw_source_id, email.sender, email.subject, email.body, email.received_at.isoformat()),
    )
    conn.commit()
    return cur.rowcount == 1


def seen_raw_email(conn: sqlite3.Connection, raw_source_id: str) -> bool:
    row = conn.execute("select 1 from raw_emails where raw_source_id = ?", (raw_source_id,)).fetchone()
    return row is not None


def upsert_listing(conn: sqlite3.Connection, listing: Listing) -> Listing:
    now = datetime.now()
    row = conn.execute("select payload, first_seen_at from listings where listing_id = ?", (listing.listing_id,)).fetchone()
    if row:
        listing.first_seen_at = datetime.fromisoformat(row["first_seen_at"])
        listing.last_seen_at = now
    else:
        listing.first_seen_at = listing.first_seen_at or now
        listing.last_seen_at = listing.last_seen_at or now
    conn.execute(
        """
        insert into listings(listing_id, payload, status, score, first_seen_at, last_seen_at)
        values (?, ?, ?, ?, ?, ?)
        on conflict(listing_id) do update set
            payload=excluded.payload,
            status=excluded.status,
            score=excluded.score,
            last_seen_at=excluded.last_seen_at
        """,
        (
            listing.listing_id,
            json.dumps(_to_payload(listing), sort_keys=True),
            listing.status.value,
            listing.score,
            listing.first_seen_at.isoformat(),
            listing.last_seen_at.isoformat(),
        ),
    )
    conn.execute(
        "insert or replace into outbox(listing_id, message, sent_at) values (?, ?, ?)",
        (listing.listing_id, listing.message, listing.auto_sent_at.isoformat() if listing.auto_sent_at else None),
    )
    conn.commit()
    return listing


def get_listing(conn: sqlite3.Connection, listing_id: str) -> Listing | None:
    row = conn.execute("select payload from listings where listing_id = ?", (listing_id,)).fetchone()
    return _from_payload(json.loads(row["payload"])) if row else None


def list_listings(conn: sqlite3.Connection, statuses: Iterable[Status] | None = None) -> list[Listing]:
    if statuses:
        status_values = [status.value for status in statuses]
        placeholders = ",".join("?" for _ in status_values)
        rows = conn.execute(f"select payload from listings where status in ({placeholders}) order by score desc", status_values).fetchall()
    else:
        rows = conn.execute("select payload from listings order by score desc").fetchall()
    return [_from_payload(json.loads(row["payload"])) for row in rows]


def set_status(conn: sqlite3.Connection, listing_id: str, status: Status) -> bool:
    listing = get_listing(conn, listing_id)
    if not listing:
        return False
    listing.status = status
    upsert_listing(conn, listing)
    return True


def _to_payload(listing: Listing) -> dict:
    data = dict(listing.__dict__)
    data["flags"] = sorted(listing.flags)
    data["status"] = listing.status.value
    for key in ["available_from", "available_to", "first_seen_at", "last_seen_at", "auto_sent_at"]:
        if data[key] is not None:
            data[key] = data[key].isoformat()
    return data


def _from_payload(data: dict) -> Listing:
    from datetime import date

    for key in ["available_from", "available_to"]:
        if data.get(key):
            data[key] = date.fromisoformat(data[key])
    for key in ["first_seen_at", "last_seen_at", "auto_sent_at"]:
        if data.get(key):
            data[key] = datetime.fromisoformat(data[key])
    data["flags"] = set(data.get("flags", []))
    data["status"] = Status(data.get("status", "new"))
    return Listing(**data)

