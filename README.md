# NYC Sublet Finder

Local Python 3.12 MVP for finding furnished NYC sublets for an Oct 1, 2026 move-in.

## What it does

- Reads Gmail alerts or local fixture emails.
- Parses Craigslist, StreetEasy, Leasebreak, newsletters, and manual pasted text.
- Normalizes listings into one model.
- Filters only clear failures: over budget, unfurnished, incompatible dates, or rejected commute.
- Scores promising listings from 0-100.
- Uses `data/nyc_nta_commute_to_broadway_astoria.csv` during normal runs. It does not call Google Maps hourly.
- Writes ready-to-send messages.
- Auto-sends only for clean direct email contacts that pass score, flag, rate-limit, and quiet-hour checks.
- Sends non-email contacts to a manual-send workflow for Google Sheets.

## Setup

Install Python 3.12, then:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
cp config.example.yaml config.yaml
```

Edit `config.yaml`, especially `messaging.phone_number`.

## Commands

```bash
python -m app.main run-once
python -m app.main run-once --dry-run
python -m app.main import-text
python -m app.main list-new
python -m app.main show LISTING_ID
python -m app.main mark-contacted LISTING_ID
python -m app.main reject LISTING_ID
python -m app.main outbox-list
python -m app.main outbox-send LISTING_ID
python -m app.main sync-sheets
```

Dry run uses fixture emails and will not send mail, modify Gmail, or write to Google Sheets.

## Gmail and Google Sheets

The production clients are thin wrappers designed to be replaced with real Gmail and Sheets API calls. Until wired, non-dry-run Gmail and Sheets commands fail clearly if credentials are missing.

Use repository or local environment secrets:

- `GMAIL_CREDENTIALS_JSON`
- `GOOGLE_SHEETS_CREDENTIALS_JSON`
- `GOOGLE_MAPS_API_KEY`, only for one-time commute table generation
- `PHONE_NUMBER`
- `ENABLE_AUTO_SEND=true`, only when you want scheduled live sends

## Commute table

Hourly runs read `data/nyc_nta_commute_to_broadway_astoria.csv`. To generate a full table later:

```bash
GOOGLE_MAPS_API_KEY=... python scripts/generate_commute_table.py nyc_nta.geojson
```

The script computes NTA centroids and calls Google Maps Distance Matrix in transit mode for a configurable weekday evening departure time.

## Alerts and imports

Set up saved searches or alerts for furnished sublets on Craigslist and StreetEasy. Newsletters or generic alerts work too, as long as the body contains useful price, date, location, link, and contact hints.

For Facebook or copied listing text:

```bash
python -m app.main import-text < pasted-listing.txt
```

## Google Sheet

Visible columns are Score, Status, Price, Area, Dates, Type, Source, Link, Message, and Flags. Internal fields are kept alongside them for dedupe, commute, contact method, send time, and raw source IDs.

Use `needs_manual_send` rows for listings that passed but cannot be automatically emailed. Open the Link, paste the exact Message, and then run `mark-contacted`.

## Tests

```bash
pytest
```

Tests run offline and use local fixture emails, sample commute data, and mockable clients.
