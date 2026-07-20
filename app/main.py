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
from app.source_client import fetch_configured_source_listings


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
    except Exception as exc:
        if _is_google_refresh_error(exc):
            print("Google credentials are expired or revoked. Re-authorize Google OAuth and update GMAIL_CREDENTIALS_JSON and GOOGLE_SHEETS_CREDENTIALS_JSON.")
            return 3
        raise
    return 1


def run_once(config: AppConfig, conn, dry_run: bool) -> int:
    client = FixtureGmailClient(config.root / "tests" / "fixtures") if dry_run else RealGmailClient()
    already_synced_raw_ids: set[str] = set()
    already_synced_listing_ids: set[str] = set()
    if not dry_run and config.section("google_sheets").get("enabled"):
        sheets_config = config.section("google_sheets")
        sheets_client = RealSheetsClient(sheets_config["spreadsheet_name"], spreadsheet_id=sheets_config.get("spreadsheet_id"))
        already_synced_raw_ids = sheets_client.existing_raw_source_ids()
        already_synced_listing_ids = sheets_client.existing_listing_ids()
    new_listings: list[Listing] = []
    gmail_config = config.section("gmail")
    fetched_emails = client.fetch_messages(gmail_config["queries"], int(gmail_config.get("max_messages_per_query", 500)))
    skipped_seen = 0
    skipped_non_housing = 0
    for email in fetched_emails:
        if db.seen_raw_email(conn, email.raw_source_id) or email.raw_source_id in already_synced_raw_ids:
            skipped_seen += 1
            continue
        if not is_housing_email(email):
            skipped_non_housing += 1
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
    print(
        f"Scanned {len(fetched_emails)} Gmail messages; skipped {skipped_non_housing} non-housing; "
        f"skipped {skipped_seen} already-seen; processed {len(new_listings)} listings."
    )
    source_listings, source_stats = fetch_configured_source_listings(
        config.section("web_sources"), fixture_dir=(config.root / "tests" / "fixtures" / "sources" if dry_run else None)
    )
    processed_sources = []
    skipped_existing_sources = 0
    for listing in process_listings(source_listings, config):
        if listing.listing_id in already_synced_listing_ids:
            skipped_existing_sources += 1
            continue
        if not dry_run:
            db.upsert_listing(conn, listing)
        processed_sources.append(listing)
    new_listings.extend(processed_sources)
    print(
        f"Scanned {source_stats.fetched_sources} web sources; fetched {source_stats.fetched_items} source items; "
        f"failed {source_stats.failed_sources} sources; skipped {skipped_existing_sources} already-seen source listings; "
        f"processed {len(processed_sources)} source listings."
    )
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
        if listing.status != Status.REJECTED:
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


def _is_google_refresh_error(exc: Exception) -> bool:
    return exc.__class__.__name__ == "RefreshError" and "expired or revoked" in str(exc).lower()


def is_housing_email(email: RawEmail) -> bool:
    sender = email.sender.lower()
    subject = email.subject.lower()
    body = email.body.lower()
    if any(blocked in sender for blocked in ["github.com", "google.com", "accounts.google.com", "myaccount.google.com"]):
        return False
    if any(blocked in body for blocked in ["myaccount.google.com/notifications", "github.com/notifications", "github.com/jacobfgilbert-png/nychousing/actions"]):
        return False
    trusted_sources = ["craigslist.org", "streeteasy.com", "leasebreak.com"]
    if any(source in sender for source in trusted_sources):
        return True
    housing_terms = ["sublet", "furnished apartment", "furnished room", "short term rental", "short-term rental", "room available"]
    noise_terms = ["security alert", "sign-in", "password", "github actions", "workflow"]
    text = f"{subject}\n{body}"
    return any(term in text for term in housing_terms) and not any(term in text for term in noise_terms)


if __name__ == "__main__":
    raise SystemExit(main())
