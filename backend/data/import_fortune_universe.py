"""Merge a Fortune 1000 CSV into Green Canopy's ticker universe.

Expected columns: Rank, Company, Ticker, Sector, Industry, CompanyType.
Rows without a usable public ticker are skipped because yfinance requires one.
Existing Green Canopy tags/exclusion metadata is preserved by ticker.

Usage:
    python backend/data/import_fortune_universe.py path/to/fortune1000.csv
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


UNIVERSE = Path(__file__).with_name("investment_universe.json")


def main(csv_path: str) -> None:
    data = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    etfs = [item for item in data["securities"] if item["type"] == "etf"]
    existing = {item["ticker"]: item for item in data["securities"] if item["type"] == "stock"}
    companies: list[dict[str, object]] = []
    seen: set[str] = set()

    with Path(csv_path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = (row.get("Ticker") or "").strip().upper().replace(".", "-")
            company_type = (row.get("CompanyType") or "").strip().lower()
            if not ticker or ticker in {"N/A", "PRIVATE"} or company_type not in {"public", ""} or ticker in seen:
                continue
            seen.add(ticker)
            prior = existing.get(ticker, {})
            companies.append({
                "ticker": ticker,
                "name": (row.get("Company") or ticker).strip(),
                "type": "stock",
                "sector": (row.get("Sector") or "Unclassified").strip(),
                "industry": (row.get("Industry") or "").strip(),
                "tags": prior.get("tags", []),
                "exclusions": prior.get("exclusions", []),
                "fortune_rank": int(float(row.get("Rank") or 0)),
                "rank": 100 + int(float(row.get("Rank") or 0)),
            })

    companies.sort(key=lambda item: int(item["fortune_rank"]))
    data["securities"] = etfs + companies
    data["scope"]["companies"] = (
        f"{len(companies)} publicly traded companies with usable tickers from the 2024 Fortune 1000 dataset; "
        "private and untickered companies are retained by the source but cannot be queried through yfinance"
    )
    data["scope"]["fortune_source"] = "Public 2024 Fortune 1000 dataset, refreshed 2024-08-05"
    UNIVERSE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(companies)} public company tickers and {len(etfs)} ETFs")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: import_fortune_universe.py path/to/fortune1000.csv")
    main(sys.argv[1])
