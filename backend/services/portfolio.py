from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.models import Allocation, InvestorProfile, PortfolioRequest, PortfolioResponse
from backend.services.investor_profile import build_profile
from backend.services.market_data import MarketDataError, MarketDataService
from backend.services.portfolio_optimizer import optimize_weights, portfolio_metrics, rounded_allocations
from backend.services.sustainability import alignment_score


UNIVERSE_PATH = Path(__file__).resolve().parents[1] / "data" / "investment_universe.json"


def load_universe() -> dict[str, Any]:
    with UNIVERSE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _candidate_score(item: dict[str, Any], profile: InvestorProfile) -> float:
    priority = profile.sustainability_priority_weights
    match = sum(priority.get(tag, 0) for tag in item.get("tags", []))
    diversified = 0.12 if item["type"] == "etf" else 0
    rank_tiebreaker = 1 / max(1, item.get("rank", 9999))
    return match * 10 + diversified + rank_tiebreaker


def select_candidates(profile: InvestorProfile, limit: int = 24) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    universe = load_universe()["securities"]
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    requested_exclusions = set(profile.exclusions)
    for item in universe:
        conflict = requested_exclusions.intersection(item.get("exclusions", []))
        if conflict:
            excluded.append({"ticker": item["ticker"], "reason": f"Matched exclusion: {', '.join(sorted(conflict))}"})
            continue
        # Leveraged funds are inappropriate for this educational long-term MVP.
        if item.get("sector") == "Leveraged Equity":
            excluded.append({"ticker": item["ticker"], "reason": "Leveraged ETF excluded by portfolio policy"})
            continue
        eligible.append(item)

    stocks = sorted((x for x in eligible if x["type"] == "stock"), key=lambda x: _candidate_score(x, profile), reverse=True)
    etfs = sorted((x for x in eligible if x["type"] == "etf"), key=lambda x: _candidate_score(x, profile), reverse=True)
    stock_slots = min(max(6, limit // 2), len(stocks))
    selected = stocks[:stock_slots] + etfs[: max(0, limit - stock_slots)]
    selected.sort(key=lambda x: _candidate_score(x, profile), reverse=True)
    return selected, excluded[:30]


def generate_portfolio(request: PortfolioRequest, market: MarketDataService) -> PortfolioResponse:
    profile = request.profile or build_profile(request.answers)  # type: ignore[arg-type]
    target_holdings = max(request.number_of_holdings, math.ceil(1 / profile.max_concentration))
    candidates, excluded = select_candidates(profile, max(24, target_holdings * 3))
    evaluated: list[dict[str, Any]] = []
    warnings: list[str] = []

    for item in candidates:
        symbol = item["ticker"]
        try:
            info = market.get_info(symbol)
            close = market.get_history(symbol)
            sustainability = market.get_sustainability(symbol)
        except MarketDataError as exc:
            excluded.append({"ticker": symbol, "reason": str(exc)})
            continue
        if item["type"] == "stock" and not sustainability:
            excluded.append({"ticker": symbol, "reason": "Yahoo sustainability data unavailable"})
            continue
        alignment = alignment_score(profile, item.get("tags", []), sustainability, item["type"])
        evaluated.append({
            **item,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector") or item.get("sector") or "Unclassified",
            "history": close,
            "sustainability": sustainability,
            "alignment": alignment,
        })
        if len(evaluated) >= target_holdings:
            break

    if len(evaluated) < 5:
        raise MarketDataError(
            "Fewer than five eligible investments had adequate market data. "
            "Try again later; Green Canopy will not fabricate missing provider data."
        )

    evaluated = evaluated[:target_holdings]
    prices = pd.concat([item["history"] for item in evaluated], axis=1, join="inner").dropna()
    if len(prices) < 60:
        raise MarketDataError("Eligible investments did not have enough overlapping price history")

    result = optimize_weights(
        prices,
        [item["alignment"]["alignment_score"] for item in evaluated],
        profile,
        profile.max_concentration,
    )
    if result.warning:
        warnings.append(result.warning)
    metrics = portfolio_metrics(prices, result.weights)
    percentages, dollars = rounded_allocations(result.weights, request.investment_amount)
    allocations: list[Allocation] = []
    for item, percent, dollars_value in zip(evaluated, percentages, dollars):
        matched = item["alignment"]["matched_priorities"]
        why = (
            f"Supports {', '.join(matched)} and adds {item['sector'].lower()} exposure."
            if matched
            else f"Adds {item['sector'].lower()} diversification while meeting financial-data requirements."
        )
        allocations.append(Allocation(
            ticker=item["ticker"],
            name=item["name"],
            asset_type=item["type"],
            sector=item["sector"],
            weight=percent,
            dollar_amount=dollars_value,
            purchase_price=round(float(item["history"].iloc[-1]), 4),
            shares=round(dollars_value / float(item["history"].iloc[-1]), 8),
            alignment_score=item["alignment"]["alignment_score"],
            confidence=item["alignment"]["confidence"],
            matched_priorities=matched,
            why_selected=why,
            sustainability_status="available" if item["sustainability"] else "unavailable",
        ))

    weighted_alignment = sum(a.alignment_score * a.weight / 100 for a in allocations)
    sector_totals: Counter[str] = Counter()
    for allocation in allocations:
        sector_totals[allocation.sector] += allocation.weight
    diversification_score = round(
        max(0, min(100, (1 - sum((value / 100) ** 2 for value in sector_totals.values())) * 125)),
        1,
    )
    retrieved_at = datetime.now(timezone.utc).isoformat()
    missing_count = sum(1 for item in allocations if item.sustainability_status == "unavailable")
    if missing_count:
        warnings.append(f"{missing_count} ETF holding(s) lack Yahoo sustainability fields; confidence was reduced.")

    return PortfolioResponse(
        investor_profile=profile,
        total_investment_amount=request.investment_amount,
        allocations=allocations,
        sustainability_alignment_score=round(weighted_alignment, 1),
        **metrics,
        number_of_holdings=len(allocations),
        sector_distribution={key: round(value, 2) for key, value in sector_totals.items()},
        diversification_score=diversification_score,
        data_retrieved_at=retrieved_at,
        sources=["Yahoo Finance via yfinance", "Green Canopy classification metadata"],
        warnings=warnings,
        limitations=[
            "Historical returns are descriptive, not forecasts or guarantees.",
            "Yahoo sustainability fields are third-party ESG risk indicators, not proof of positive impact.",
            "Green Canopy alignment is a transparent educational score, not a third-party ESG rating.",
            "This educational simulation is not financial advice and does not execute trades.",
        ],
        excluded_investments=excluded[:50],
    )
