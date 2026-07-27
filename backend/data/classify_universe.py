"""Systematically classify untagged stocks in the Green Canopy universe.

Reads each stock's own business description from yfinance and checks it against a
curated set of specific, differentiating phrases per category (deliberately stricter
than the app's live "supporting evidence" keyword list, which is fine to be lenient
since it only explains an already-assigned tag rather than deciding whether to assign
one). Existing tags are never overwritten -- only stocks with no tags are touched.

Default mode is a dry run: it prints what it would assign without writing anything.
Pass --apply to write the results back into investment_universe.json.
Pass --limit N to cap how many untagged stocks are processed (useful for test runs).
Pass --tickers A,B,C to classify a specific list instead of scanning in order.

Usage:
    python backend/data/classify_universe.py --limit 25
    python backend/data/classify_universe.py --tickers ADM,WY,GE,DOW --apply
    python backend/data/classify_universe.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.market_data import split_sentences  # noqa: E402


UNIVERSE_PATH = Path(__file__).with_name("investment_universe.json")
CHECKPOINT_PATH = Path(__file__).with_name(".classify_checkpoint.json")

# Deliberately stricter and more specific than the app's live TAG_KEYWORDS (used only
# to find supporting evidence for an already-assigned tag). Generic single words like
# "employee" or "compliance" appear in almost every company's boilerplate and would
# over-tag nearly the whole universe if used here, so classification requires more
# specific, differentiating phrases.
CLASSIFICATION_KEYWORDS = {
    "climate": [
        "climate change", "carbon emission", "carbon capture", "carbon sequestration", "carbon footprint",
        "greenhouse gas", "emissions reduction", "emission reduction", "net zero", "net-zero", "decarboniz",
        "renewable energy", "renewable generation", "clean energy", "solar power", "solar energy", "wind power",
        "wind energy", "low-carbon", "low carbon",
    ],
    "renewable_energy": [
        "renewable energy", "renewable generation", "solar power", "solar energy", "solar farm", "wind power",
        "wind energy", "wind farm", "geothermal", "battery storage", "hydroelectric", "clean energy generation",
    ],
    "fair_labor": [
        "workplace safety", "fair wage", "collective bargaining", "labor union", "employee training program",
        "occupational health and safety", "diversity and inclusion program", "employee wellbeing", "workforce safety",
    ],
    "human_rights": [
        "human rights", "forced labor", "modern slavery", "child labor", "ethical sourcing", "responsible sourcing",
        "supply chain labor",
    ],
    "biodiversity": [
        "biodiversity", "wildlife conservation", "habitat conservation", "ecosystem restoration", "deforestation",
        "reforestation", "endangered species", "land conservation", "forest management", "forest stewardship",
        "sustainable forestry", "sustainably managed forest",
    ],
    "clean_water": [
        "water conservation", "water treatment", "wastewater treatment", "water quality", "water scarcity",
        "water stewardship", "watershed protection", "clean water",
    ],
    "sustainable_agriculture": [
        "sustainable agriculture", "sustainable farming", "regenerative agriculture", "organic farming",
        "soil health", "land stewardship", "agricultural raw material", "agricultural commodit",
        "crop production", "farming operation",
    ],
    "circular_economy": [
        "circular economy", "recycling program", "waste reduction", "zero waste", "upcycl", "materials recovery",
        "sustainable packaging", "recyclable packaging", "reduce waste",
    ],
    "governance": [
        "corporate governance", "code of conduct", "anti-corruption", "whistleblower", "board diversity",
        "executive compensation policy", "board of directors' oversight", "ethics and compliance program",
    ],
}


def classify_summary(summary: str | None) -> dict[str, list[str]]:
    """Return {tag: [matching sentences]} for a business summary, using the whole text."""
    if not summary:
        return {}
    sentences = split_sentences(summary)
    matches: dict[str, list[str]] = {}
    for tag, phrases in CLASSIFICATION_KEYWORDS.items():
        hits = [s for s in sentences if any(phrase in s.lower() for phrase in phrases)]
        if hits:
            matches[tag] = hits
    return matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of untagged stocks processed")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated list of tickers to classify")
    parser.add_argument("--apply", action="store_true", help="Write results back into investment_universe.json")
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds to wait between yfinance requests")
    parser.add_argument("--fresh", action="store_true", help="Ignore any existing checkpoint and start over")
    args = parser.parse_args()

    data = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    securities = data["securities"]
    by_ticker = {s["ticker"]: s for s in securities}

    if args.tickers:
        targets = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        targets = [s["ticker"] for s in securities if s["type"] == "stock" and not s.get("tags")]
        if args.limit:
            targets = targets[: args.limit]

    results: dict[str, list[str]] = {}
    if not args.fresh and CHECKPOINT_PATH.exists():
        results = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        already_done = set(results.keys())
        remaining = [t for t in targets if t not in already_done]
        print(f"Resuming from checkpoint: {len(already_done)} already done, {len(remaining)} remaining.\n")
        targets = remaining

    print(f"Classifying {len(targets)} stock(s){' (dry run, no changes will be saved)' if not args.apply else ''}\n")

    for i, ticker in enumerate(targets):
        item = by_ticker.get(ticker)
        if not item or item.get("tags"):
            continue
        try:
            info = yf.Ticker(ticker).get_info()
        except Exception as exc:
            print(f"[{i+1}/{len(targets)}] {ticker}: ERROR fetching data ({exc})")
            continue
        summary = info.get("longBusinessSummary")
        matches = classify_summary(summary)
        tags = sorted(matches.keys())
        results[ticker] = tags
        CHECKPOINT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

        label = item.get("name", ticker)
        industry = item.get("industry", "?")
        if tags:
            print(f"[{i+1}/{len(targets)}] {ticker} ({label}, {industry}) -> {tags}")
            for tag, sentences in matches.items():
                print(f"    {tag}: \"{sentences[0]}\"")
        else:
            print(f"[{i+1}/{len(targets)}] {ticker} ({label}, {industry}) -> no tags matched")

        if i < len(targets) - 1:
            time.sleep(args.delay)

    matched_count = sum(1 for tags in results.values() if tags)
    print(f"\n{matched_count}/{len(results)} stocks matched at least one tag.")

    if args.apply:
        for ticker, tags in results.items():
            if tags:
                by_ticker[ticker]["tags"] = tags
        UNIVERSE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote updated tags for {matched_count} stock(s) to {UNIVERSE_PATH.name}")
        if CHECKPOINT_PATH.exists():
            CHECKPOINT_PATH.unlink()
    else:
        print(f"Dry run only -- rerun with --apply to save these tags. Checkpoint saved to {CHECKPOINT_PATH.name}.")


if __name__ == "__main__":
    main()
