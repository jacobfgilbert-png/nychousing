from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommuteEntry:
    nta_name: str
    borough: str
    centroid_lat: float
    centroid_lon: float
    commute_minutes: int
    commute_bucket: str


def load_commute_table(path: str | Path) -> dict[str, CommuteEntry]:
    entries: dict[str, CommuteEntry] = {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            entry = CommuteEntry(
                nta_name=row["nta_name"],
                borough=row["borough"],
                centroid_lat=float(row["centroid_lat"]),
                centroid_lon=float(row["centroid_lon"]),
                commute_minutes=int(row["commute_minutes"]),
                commute_bucket=row["commute_bucket"],
            )
            entries[entry.nta_name.lower()] = entry
    return entries


def bucket_for_minutes(minutes: int) -> str:
    if minutes <= 45:
        return "excellent"
    if minutes <= 60:
        return "acceptable"
    if minutes <= 75:
        return "weak"
    return "reject"
