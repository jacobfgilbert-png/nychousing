from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an NYC NTA transit commute table.")
    parser.add_argument("geojson", help="NYC Planning NTA GeoJSON path")
    parser.add_argument("--output", default="data/nyc_nta_commute_to_broadway_astoria.csv")
    parser.add_argument("--destination", default="Broadway, Astoria, Queens, NY")
    parser.add_argument("--departure", default="2026-10-06T18:00:00", help="Weekday evening local datetime")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key and not args.dry_run:
        print("GOOGLE_MAPS_API_KEY is required to generate the real commute table.")
        return 2

    features = json.loads(Path(args.geojson).read_text(encoding="utf-8"))["features"]
    rows = []
    for feature in features:
        name = feature["properties"].get("ntaname") or feature["properties"].get("NTAName") or feature["properties"].get("name")
        borough = feature["properties"].get("boro_name") or feature["properties"].get("BoroName") or ""
        lat, lon = centroid(feature["geometry"])
        minutes = 0 if args.dry_run else google_distance_minutes(lat, lon, args.destination, args.departure, api_key or "")
        rows.append(
            {
                "nta_name": name,
                "borough": borough,
                "centroid_lat": f"{lat:.6f}",
                "centroid_lon": f"{lon:.6f}",
                "commute_minutes": minutes,
                "commute_bucket": bucket_for_minutes(minutes),
            }
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["nta_name", "borough", "centroid_lat", "centroid_lon", "commute_minutes", "commute_bucket"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output}.")
    return 0


def centroid(geometry: dict) -> tuple[float, float]:
    coords = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        points = coords[0]
    elif geometry["type"] == "MultiPolygon":
        points = max(coords, key=lambda poly: len(poly[0]))[0]
    else:
        raise ValueError(f"Unsupported geometry type: {geometry['type']}")
    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return lat, lon


def google_distance_minutes(lat: float, lon: float, destination: str, departure: str, api_key: str) -> int:
    departure_ts = int(datetime.fromisoformat(departure).timestamp())
    params = urlencode(
        {
            "origins": f"{lat},{lon}",
            "destinations": destination,
            "mode": "transit",
            "departure_time": departure_ts,
            "key": api_key,
        }
    )
    with urlopen(f"https://maps.googleapis.com/maps/api/distancematrix/json?{params}", timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    element = payload["rows"][0]["elements"][0]
    if element["status"] != "OK":
        raise RuntimeError(f"Distance Matrix failed for {lat},{lon}: {element['status']}")
    return round(element["duration"]["value"] / 60)


def bucket_for_minutes(minutes: int) -> str:
    if minutes <= 45:
        return "excellent"
    if minutes <= 60:
        return "acceptable"
    if minutes <= 75:
        return "weak"
    return "reject"


if __name__ == "__main__":
    raise SystemExit(main())

