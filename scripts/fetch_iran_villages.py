"""Fetch and compact the complete village directory for the deployment package.

Source: sajaddp/list-of-cities-in-Iran, generated from the official Iranian
administrative-divisions workbook for year 1404. This file is intentionally
generated during deployment rather than committed as a 31 MB JSON blob.
"""
import gzip
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "kidareh" / "data" / "villages.json.gz"
SOURCE = (
    "https://raw.githubusercontent.com/sajaddp/list-of-cities-in-Iran/"
    "ace21bb251f96ced350bbc01541acffd71121feb/dist/json/villages.json"
)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "Kidareh-IranLocations/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        records = json.load(response)
    if not isinstance(records, list) or len(records) < 90000:
        raise SystemExit("Village source validation failed; refusing to deploy an incomplete directory.")
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as target:
        json.dump(records, target, ensure_ascii=False, separators=(",", ":"))
    print(f"Prepared {len(records):,} Iranian villages at {OUTPUT}.")


if __name__ == "__main__":
    main()
