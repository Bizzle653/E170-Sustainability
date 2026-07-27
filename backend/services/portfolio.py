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
from backend.services.market_data import MarketDataError, MarketDataService, first_sentence
from backend.services.portfolio_optimizer import optimize_weights, portfolio_metrics, rounded_allocations
from backend.services.sustainability import alignment_score, compose_fund_snapshot


UNIVERSE_PATH = Path(__file__).resolve().parents[1] / "data" / "investment_universe.json"

# How much a candidate's historical risk-adjusted performance competes with its values
# alignment when deciding which securities make the final cut, keyed off the same
# sustainability_tradeoff answer already used by the optimizer's objective function.
# Values-alignment always keeps at least a strong plurality -- even "none" tradeoff
# stays under 50% financial weight, since this is a values-based tool first.
FINANCIAL_WEIGHT_BY_TRADEOFF = {
    "none": 0.45,
    "small": 0.30,
    "moderate": 0.18,
    "strong": 0.08,
}


def load_universe() -> dict[str, Any]:
    with UNIVERSE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _percentile_ranks(values: list[float]) -> list[float]:
    """Rank-based 0..1 normalization so scores on different scales (a 0-100 alignment
    score vs. an unbounded risk-adjusted return) can be blended without one dominating
    just because of its units."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    denominator = max(1, len(values) - 1)
    for position, index in enumerate(order):
        ranks[index] = position / denominator
    return ranks


def _candidate_score(item: dict[str, Any], profile: InvestorProfile) -> float:
    priority = profile.sustainability_priority_weights
    match = sum(priority.get(tag, 0) for tag in item.get("tags", []))
    diversified = 0.12 if item["type"] == "etf" else 0
    # A small nudge among otherwise-equal candidates. ETF and stock "rank" come from
    # different scales (ETF: 1-100 by assets, stock: 1-1055 combined universe rank), so
    # this must stay tiny — at full weight it let top-asset ETFs (rank 1) outscore a real
    # priority-tag match and crowd every individual stock out of recommendations.
    rank_tiebreaker = 1 / (100 * max(1, item.get("rank", 9999)))
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
    # Deliberately not re-sorted by score afterward: that used to erase this stock
    # reservation, since ETF "rank" (1-100, dense) beats stock "rank" (up to 1055,
    # sparse) as a tiebreaker on almost every tie, letting ETFs silently crowd out
    # every individual stock once evaluation stops at the requested holding count.
    return stocks[:stock_slots] + etfs[: max(0, limit - stock_slots)], excluded[:30]


def generate_portfolio(request: PortfolioRequest, market: MarketDataService) -> PortfolioResponse:
    profile = request.profile or build_profile(request.answers)  # type: ignore[arg-type]
    active_priorities = [key for key, weight in profile.sustainability_priority_weights.items() if weight > 0]
    universe_by_ticker = {item["ticker"]: item for item in load_universe()["securities"]}
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
            candidate_metrics = MarketDataService.metrics(close)
        except MarketDataError as exc:
            excluded.append({"ticker": symbol, "reason": str(exc)})
            continue
        business_summary = None
        fund_evidence: dict[str, str] = {}
        if item["type"] == "stock":
            business_summary = first_sentence(info.get("longBusinessSummary"))
        else:
            holdings = market.get_top_holdings(symbol)
            business_summary, fund_evidence = compose_fund_snapshot(holdings, universe_by_ticker, active_priorities)
        alignment = alignment_score(
            profile, item.get("tags", []), sustainability, item["type"],
            info.get("longBusinessSummary"), fund_evidence,
        )
        # A simple historical risk-adjusted return (return per unit of volatility) --
        # the same idea as a Sharpe ratio, used only to rank candidates against each
        # other, not shown to the user as a formal risk-adjusted metric.
        risk_adjusted_return = candidate_metrics["annualized_historical_return"] / max(
            candidate_metrics["annualized_volatility"], 0.01
        )
        evaluated.append({
            **item,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector") or item.get("sector") or "Unclassified",
            "history": close,
            "sustainability": sustainability,
            "alignment": alignment,
            "business_summary": business_summary,
            "risk_adjusted_return": risk_adjusted_return,
        })

    if len(evaluated) < 5:
        raise MarketDataError(
            "Fewer than five eligible investments had adequate market data. "
            "Try again later; Green Canopy will not fabricate missing provider data."
        )

    # Blend values-alignment with historical risk-adjusted performance to choose the
    # final holdings, rather than relying on tag-match order alone. Financial weight is
    # tied to the user's own sustainability_tradeoff answer so the blend reflects what
    # they actually said they'd accept, not an arbitrary fixed ratio.
    financial_weight = FINANCIAL_WEIGHT_BY_TRADEOFF.get(profile.sustainability_tradeoff, 0.18)
    alignment_ranks = _percentile_ranks([item["alignment"]["alignment_score"] for item in evaluated])
    financial_ranks = _percentile_ranks([item["risk_adjusted_return"] for item in evaluated])
    for item, alignment_rank, financial_rank in zip(evaluated, alignment_ranks, financial_ranks):
        item["blended_rank"] = financial_weight * financial_rank + (1 - financial_weight) * alignment_rank
    evaluated.sort(key=lambda item: item["blended_rank"], reverse=True)
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
            detail=item["alignment"]["detail"],
            business_summary=item["business_summary"],
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
            "Green Canopy alignment is a transparent educational score based on classification tags, not a third-party ESG rating.",
            "This educational simulation is not financial advice and does not execute trades.",
        ],
        excluded_investments=excluded[:50],
    )
