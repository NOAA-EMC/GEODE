#!/usr/bin/env python3
"""Download the BUFR file for the cycle nearest to 12 hours ago (UTC)."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen


def nearest_cycle_time(now_utc: datetime) -> datetime:
    """Return the nearest synoptic cycle (00, 06, 12, 18) to now_utc - 12 hours."""
    target = now_utc - timedelta(hours=12)
    cycle_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
    candidates = [cycle_start + timedelta(hours=h) for h in (0, 6, 12, 18)]

    prev_day_cycle = cycle_start - timedelta(hours=6)
    next_day_cycle = cycle_start + timedelta(days=1)
    candidates.extend([prev_day_cycle, next_day_cycle])

    return min(candidates, key=lambda dt: (abs(dt - target), dt))


def build_bufr_url(cycle_time: datetime) -> str:
    """Construct the NOMADS BUFR URL for the given cycle time."""
    ymd = cycle_time.strftime("%Y%m%d")
    hh = cycle_time.strftime("%H")
    return (
        "https://nomads.ncep.noaa.gov/pub/data/nccf/com/obsproc/prod/"
        f"gfs.{ymd}/gfs.t{hh}z.uprair.tm00.bufr_d"
    )


def download_file(url: str,output_path: Path) -> None:
    """Download URL content to output_path."""
    with urlopen(url) as response, output_path.open("wb") as out_file:
        out_file.write(response.read())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the uprair BUFR file for the cycle nearest to "
            "12 hours ago in UTC."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory where the BUFR file will be saved (default: current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the URL and output path without downloading.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now_utc = datetime.now(timezone.utc)
    cycle_time = nearest_cycle_time(now_utc)
    url = build_bufr_url(cycle_time)

    filename = Path(url).name
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    print(f"Current UTC time: {now_utc:%Y-%m-%d %H:%M:%S %Z}")
    print(f"Selected cycle:   {cycle_time:%Y-%m-%d %H:%M UTC}")
    print(f"Source URL:       {url}")
    print(f"Output file:      {output_path}")

    if args.dry_run:
        return

    download_file(url, output_path)
    print("Download complete.")


if __name__ == "__main__":
    main()
