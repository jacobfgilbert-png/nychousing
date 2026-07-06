from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import db
from app.config import AppConfig, load_config
from app.dedupe import is_duplicate
from app.draft_message import build_message
from app.filters import apply_filters
from app.gmail_client import FixtureGmailClient, MissingGmailCredentials, RealGmailClient
from app.location import apply_location
from app.models import Listing, RawEmail, Status
from app.normalize import normalize_listing
from app.outbox import mark_sent, prepare_outbox
from app.parsers import parse_craigslist, parse_generic, parse_manual, parse_streeteasy
from app.scoring import score_listing
from app.sheets_client import MemorySheetsClient, MissingSheetsCredentials, RealSheetsClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nyc-sublet-finder")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--db", default="sublets.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-once")
    run.add_argument("--dry-run", action="store_true")
    sub.add_parser("import-text")
    sub.add_parser("list-new")
    show = sub.add_parser("show")
    show.add_argument("listing_id")
    contacted = sub.add_parser("mark-contacted")
    contacted.add_argument("listing_id")
    reject = sub.add_parser("reject")
    reject.add_argument("listing_id")
    sub.add_parser("outbox-list")
    send = sub.add_parser("outbox-send")
    send.add_argument("listing_id")
    sync = sub.add_parser("sync-sheets")
    sync.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = load_config(args.config, root=root)
    conn = db.connect(root / args.db)
    try:
        if args.command == "run-once":
            return run_once(config, conn, dry_run=args.dry_run)
        if args.command == "import-text":
            text = sys.stdin.read()
            listings = process_listings(parse_manual(text), config)
            for listing in listings:
                db.upsert_listing(conn, listing)
            print_summary(listings, dry_run=False)
            return 0
        if args.command == "list-new":
            print_listings(db.list_listings(conn, [Status.NEW, Status.NEEDS_MANUAL_SEND]))
            return 0
        if args.command == "show":
            listing = db.get_listing(conn, args.listing_id)
            if not listing:
                print("Listing not found.")
                return 1
            print_listing(listing)
            return 0
        if args.command == "mark-contacted":
            return 0 if _set_status(conn, args.listing_id, Status.CONTACTED) else 1
        if args.command == "reject":
            return 0 if _set_status(conn, args.listing_id, Status.REJECTED) else 1
        if args.command == "outbox-list":
            print_listings(db.list_listings(conn, [Status.NEEDS_MANUAL_SEND, Status.NEW]))
            return 0
        if args.command == "outbox-send":
            return outbox_send(config, conn, args.listing_id)
        if args.command == "sync-sheets":
            return sync_sheets(config, conn, dry_run=args.dry_run)
    except (MissingGmailCredentials, MissingSheetsCredentials) as exc:
        print(str(exc))
        return 2
    return 1


def run_once(config: AppConfig, conn, dry_run: bool) -> int:
    client = FixtureGmailClient(config.root / "tests" / "fixtures") if dry_run else RealGmailClient()
    new_listings: list[Listing] = []
    for email in client.fetch_messages(config.section("gmail")["queries"]):
        if db.seen_raw_email(conn, email.raw_source_id):
            continue
        if not dry_run:
            db.save_raw_email(conn, email)
        listings = process_email(email, config)
        for listing in listings:
            if not dry_run and listing.status == Status.NEW and listing.contact_email:
                client.send_email(listing.contact_email, f"Sublet inquiry: {listing.title}", listing.message)
                listing = mark_sent(listing)
            if not dry_run:
                db.upsert_listing(conn, listing)
        new_listings.extend(listings)
    print_summary(new_listings, dry_run=dry_run)
    return 0


def process_email(email: RawEmail, config: AppConfig) -> list[Listing]:
    sender = email.sender.lower()
    if "craigslist" in sender:
        parsed = parse_craigslist(email.body, email.subject)
    elif "streeteasy" in sender:
        parsed = parse_streeteasy(email.body, email.subject)
    else:
        parsed = parse_generic(email.body, subject=email.subject)
    for listing in parsed:
        listing.raw_source_id = email.raw_source_id
    return process_listings(parsed, config)


def process_listings(listings: list[Listing], config: AppConfig) -> list[Listing]:
    processed: list[Listing] = []
    for listing in listings:
        listing = normalize_listing(listing)
        listing = apply_location(listing, config)
        listing = apply_filters(listing, config)
        listing = score_listing(listing, config)
        listing.message = build_message(listing, config)
        listing = prepare_outbox(listing, config)
        processed.append(listing)
    return processed


def outbox_send(config: AppConfig, conn, listing_id: str) -> int:
    listing = db.get_listing(conn, listing_id)
    if not listing:
        print("Listing not found.")
        return 1
    if not listing.contact_email:
        print("Listing has no clean direct email address; use manual send.")
        return 1
    client = RealGmailClient()
    client.send_email(listing.contact_email, f"Sublet inquiry: {listing.title}", listing.message)
    db.upsert_listing(conn, mark_sent(listing))
    print("Sent and logged.")
    return 0


def sync_sheets(config: AppConfig, conn, dry_run: bool = False) -> int:
    listings = db.list_listings(conn)
    if dry_run:
        client = MemorySheetsClient()
        client.upsert_listings(listings)
        print(f"Dry run: would sync {len(client.rows)} rows to Google Sheets.")
        return 0
    sheets_config = config.section("google_sheets")
    client = RealSheetsClient(sheets_config["spreadsheet_name"], spreadsheet_id=sheets_config.get("spreadsheet_id"))
    client.upsert_listings(listings)
    print(f"Synced {len(listings)} rows.")
    return 0


def print_summary(listings: list[Listing], dry_run: bool) -> None:
    prefix = "Dry run: " if dry_run else ""
    print(f"{prefix}processed {len(listings)} listings.")
    print_listings(listings)


def print_listings(listings: list[Listing]) -> None:
    for listing in listings:
        print(f"{listing.listing_id} | {listing.score:3} | {listing.status.value:17} | {listing.title} | {listing.url}")


def print_listing(listing: Listing) -> None:
    print(f"{listing.title}\nID: {listing.listing_id}\nScore: {listing.score}\nStatus: {listing.status.value}\nURL: {listing.url}")
    print(f"Flags: {', '.join(sorted(listing.flags))}")
    print(f"Message:\n{listing.message}")
    print("Reasons:")
    for reason in listing.reasons:
        print(f"- {reason}")


def _set_status(conn, listing_id: str, status: Status) -> bool:
    if db.set_status(conn, listing_id, status):
        print(f"Marked {listing_id} as {status.value}.")
        return True
    print("Listing not found.")
    return False


if __name__ == "__main__":
    raise SystemExit(main())
