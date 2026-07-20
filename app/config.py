from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "search": {
        "move_in_date": "2026-10-01",
        "move_in_flex_days": 10,
        "min_stay_days": 30,
        "max_stay_days": 93,
        "max_monthly_price": 2500,
        "furnished_required": True,
        "room_ok": True,
        "whole_place_preferred": True,
        "user_has_pets": False,
    },
    "location": {
        "commute_target": "Broadway, Astoria, Queens, NY",
        "commute_table_path": "data/nyc_nta_commute_to_broadway_astoria.csv",
        "aliases_path": "data/neighborhood_aliases.yaml",
        "excellent_commute_max_minutes": 45,
        "acceptable_commute_max_minutes": 60,
        "weak_commute_max_minutes": 75,
        "favorite_neighborhoods": ["Astoria", "Inwood", "Jackson Heights", "Forest Hills"],
    },
    "messaging": {
        "mode": "auto_send_clean_email_only",
        "phone_number": "",
        "auto_send_min_score": 80,
        "max_auto_sends_per_hour": 5,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    },
    "gmail": {
        "max_messages_per_query": 1000,
        "queries": [
            'from:(craigslist.org) newer_than:30d',
            'from:(streeteasy.com) newer_than:30d',
            'from:(leasebreak.com) newer_than:30d',
            'from:(listingsproject.com) newer_than:30d',
            '("sublet" OR "sublease" OR "furnished apartment" OR "furnished room" OR "short term rental" OR "short-term rental" OR "temporary housing" OR "room available") newer_than:30d',
        ]
    },
    "web_sources": {
        "enabled": True,
        "rss_feeds": [
            {
                "name": "Craigslist NYC sublets furnished",
                "source": "craigslist",
                "url": "https://newyork.craigslist.org/search/sub?query=furnished%20sublet&max_price=2500&availabilityMode=0&format=rss",
            },
            {
                "name": "Craigslist NYC rooms furnished",
                "source": "craigslist",
                "url": "https://newyork.craigslist.org/search/roo?query=furnished%20room&max_price=2500&availabilityMode=0&format=rss",
            },
            {
                "name": "Craigslist Astoria furnished",
                "source": "craigslist",
                "url": "https://newyork.craigslist.org/search/sub?query=astoria%20furnished&max_price=2500&availabilityMode=0&format=rss",
            },
            {
                "name": "Craigslist Inwood furnished",
                "source": "craigslist",
                "url": "https://newyork.craigslist.org/search/sub?query=inwood%20furnished&max_price=2500&availabilityMode=0&format=rss",
            },
            {
                "name": "Craigslist Jackson Heights furnished",
                "source": "craigslist",
                "url": "https://newyork.craigslist.org/search/sub?query=jackson%20heights%20furnished&max_price=2500&availabilityMode=0&format=rss",
            },
            {
                "name": "Craigslist Forest Hills furnished",
                "source": "craigslist",
                "url": "https://newyork.craigslist.org/search/sub?query=forest%20hills%20furnished&max_price=2500&availabilityMode=0&format=rss",
            },
        ],
    },
    "bulk_import": {"enabled": True, "import_dir": "data/imports"},
    "yerr": {
        "enabled": True,
        "base_url": "https://yerr.org/api/listings",
        "max_price": 2500,
        "listing_types": ["sublet", "lease_break"],
        "source_platforms": ["reddit", "facebook", "craigslist", "listingproject"],
        "limit": 100,
        "max_pages": 10,
    },
    "google_sheets": {"enabled": True, "spreadsheet_name": "NYC Sublet Finder"},
    "notifications": {"email_digest": True, "immediate_min_score": 85, "digest_min_score": 70},
}


@dataclass(frozen=True)
class AppConfig:
    values: dict[str, Any]
    root: Path

    def section(self, name: str) -> dict[str, Any]:
        return self.values.get(name, {})


def load_config(path: str | Path = "config.yaml", root: str | Path | None = None) -> AppConfig:
    project_root = Path(root or Path.cwd()).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = project_root / config_path
    values = _deepcopy(DEFAULT_CONFIG)
    if config_path.exists():
        values = _deep_merge(values, _load_yaml_like(config_path.read_text(encoding="utf-8")))
    _apply_env_overrides(values)
    return AppConfig(values=values, root=project_root)


def resolve_path(config: AppConfig, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else config.root / path


def _deepcopy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deepcopy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deepcopy(v) for v in value]
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _load_yaml_like(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except Exception:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    pending_key: tuple[int, dict[str, Any], str] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            if pending_key and pending_key[0] == indent:
                _, mapping, key = pending_key
                mapping[key] = []
                parent = mapping[key]
                stack.append((indent - 1, parent))
                pending_key = None
            parent.append(_coerce(line[2:].strip()))
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
            pending_key = (indent + 2, parent, key)
        else:
            parent[key] = _coerce(value)
            pending_key = None
    return root


def _coerce(value: str) -> Any:
    value = value.strip().strip("'").strip('"')
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        return value


def _apply_env_overrides(values: dict[str, Any]) -> None:
    if os.getenv("PHONE_NUMBER"):
        values["messaging"]["phone_number"] = os.environ["PHONE_NUMBER"]
    if os.getenv("ENABLE_AUTO_SEND", "").lower() == "true":
        values["messaging"]["mode"] = "auto_send_clean_email_only"
    if os.getenv("AUTO_SEND_MIN_SCORE"):
        values["messaging"]["auto_send_min_score"] = int(os.environ["AUTO_SEND_MIN_SCORE"])
    if os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID"):
        values["google_sheets"]["spreadsheet_id"] = os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"]
