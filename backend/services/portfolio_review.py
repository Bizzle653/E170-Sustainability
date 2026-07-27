from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from backend.models import (
    HoldingAssessment,
    InvestorProfile,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    SuggestedHolding,
)
from backend.services.investor_profile import build_profile
from backend.services.market_data import MarketDataError, MarketDataService, first_sentence
from backend.services.portfolio import benchmark_comparison, load_universe, select_candidates
from backend.services.portfolio_optimizer import portfolio_metrics
from backend.services.sustainability import alignment_score, compose_fund_snapshot, compose_portfolio_narrative


ALIGNMENT_FLAG_THRESHOLD = 45


def _asset_type(universe_item: dict[str, Any] | None, info: dict[str, Any]) -> str:
    if universe_item:
        return universe_item["type"]
    return "etf" if info.get("quoteType") == "ETF" else "stock"


def _evaluate_holdings(
    request: PortfolioAnalysisRequest,
    profile: InvestorProfile,
    market: MarketDataService,
    universe_by_ticker: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    evaluated: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()

    for holding in request.holdings:
        symbol = holding.ticker.upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        try:
            info = market.get_info(symbol)
            close = market.get_history(symbol)
            sustainability = market.get_sustainability(symbol)
        except MarketDataError as exc:
            excluded.append({"ticker": symbol, "reason": str(exc)})
            continue
        universe_item = universe_by_ticker.get(symbol)
        asset_type = _asset_type(universe_item, info)
        tags = universe_item.get("tags", []) if universe_item else []
        sector = info.get("sector") or (universe_item.get("sector") if universe_item else None) or "Unclassified"
        name = info.get("longName") or info.get("shortName") or symbol
        business_summary = None
        fund_evidence: dict[str, str] = {}
        if asset_type == "stock":
            business_summary = first_sentence(info.get("longBusinessSummary"))
        else:
            active_priorities = [key for key, weight in profile.sustainability_priority_weights.items() if weight > 0]
            fund_holdings = market.get_top_holdings(symbol)
            business_summary, fund_evidence = compose_fund_snapshot(fund_holdings, universe_by_ticker, active_priorities)
        assessment = alignment_score(profile, tags, sustainability, asset_type, info.get("longBusinessSummary"), fund_evidence)
        evaluated.append({
            "ticker": symbol,
            "name": name,
            "asset_type": asset_type,
            "sector": sector,
            "dollar_amount": holding.dollar_amount,
            "in_green_canopy_universe": universe_item is not None,
            "sustainability_status": "available" if sustainability else "unavailable",
            "assessment": assessment,
            "business_summary": business_summary,
            "history": close,
        })

    return evaluated, excluded


def _build_suggestions(
    profile: InvestorProfile,
    candidates: list[dict[str, Any]],
    held_tickers: set[str],
    market: MarketDataService,
    universe_by_ticker: dict[str, dict[str, Any]],
    limit: int = 3,
) -> list[SuggestedHolding]:
    suggestions: list[SuggestedHolding] = []
    used_sectors: set[str] = set()
    for candidate in candidates:
        if len(suggestions) >= limit:
            break
        symbol = candidate["ticker"]
        if symbol in held_tickers:
            continue
        try:
            info = market.get_info(symbol)
            market.get_history(symbol)
            sustainability = market.get_sustainability(symbol)
        except MarketDataError:
            continue
        if candidate["type"] == "stock" and not sustainability:
            continue
        sector = info.get("sector") or candidate.get("sector") or "Unclassified"
        # Skip a sector already represented so the 3 suggestions are genuinely
        # different ideas, not near-duplicate large-cap growth funds.
        if sector in used_sectors:
            continue
        business_summary = None
        fund_evidence: dict[str, str] = {}
        if candidate["type"] == "stock":
            business_summary = first_sentence(info.get("longBusinessSummary"))
        else:
            active_priorities = [key for key, weight in profile.sustainability_priority_weights.items() if weight > 0]
            fund_holdings = market.get_top_holdings(symbol)
            business_summary, fund_evidence = compose_fund_snapshot(fund_holdings, universe_by_ticker, active_priorities)
        assessment = alignment_score(profile, candidate.get("tags", []), sustainability, candidate["type"], info.get("longBusinessSummary"), fund_evidence)
        matched = assessment["matched_priorities"]
        if not matched:
            continue
        used_sectors.add(sector)
        suggestions.append(SuggestedHolding(
            ticker=symbol,
            name=info.get("longName") or info.get("shortName") or symbol,
            asset_type=candidate["type"],
            sector=sector,
            alignment_score=assessment["alignment_score"],
            matched_priorities=matched,
            why_suggested=f"Supports {', '.join(matched)}, which you weren't otherwise holding.",
            detail=assessment["detail"],
            business_summary=business_summary,
        ))
    return suggestions


def analyze_portfolio(request: PortfolioAnalysisRequest, market: MarketDataService) -> PortfolioAnalysisResponse:
    profile: InvestorProfile = request.profile or build_profile(request.answers)  # type: ignore[arg-type]
    universe_by_ticker = {item["ticker"]: item for item in load_universe()["securities"]}

    evaluated, excluded = _evaluate_holdings(request, profile, market, universe_by_ticker)
    if not evaluated:
        raise MarketDataError(
            "None of the supplied tickers had usable market data. "
            "Green Canopy will not fabricate missing provider data."
        )

    total_value = sum(item["dollar_amount"] for item in evaluated)
    holdings: list[HoldingAssessment] = []
    sector_totals: Counter[str] = Counter()
    weighted_alignment = 0.0

    for item in evaluated:
        weight = round(item["dollar_amount"] / total_value * 100, 2)
        score = item["assessment"]["alignment_score"]
        flag = None
        if score < ALIGNMENT_FLAG_THRESHOLD:
            flag = "Limited alignment with your priorities"
        elif not item["assessment"]["matched_priorities"]:
            flag = "Doesn't match any of your selected priorities"
        holdings.append(HoldingAssessment(
            ticker=item["ticker"],
            name=item["name"],
            asset_type=item["asset_type"],
            sector=item["sector"],
            dollar_amount=item["dollar_amount"],
            weight=weight,
            alignment_score=score,
            confidence=item["assessment"]["confidence"],
            matched_priorities=item["assessment"]["matched_priorities"],
            sustainability_status=item["sustainability_status"],
            in_green_canopy_universe=item["in_green_canopy_universe"],
            flag=flag,
            detail=item["assessment"]["detail"],
            business_summary=item["business_summary"],
        ))
        sector_totals[item["sector"]] += weight
        weighted_alignment += score * weight / 100

    diversification_score = round(
        max(0, min(100, (1 - sum((value / 100) ** 2 for value in sector_totals.values())) * 125)),
        1,
    )

    held_tickers = {item["ticker"] for item in evaluated}
    candidates, _ = select_candidates(profile, limit=30)
    suggestions = _build_suggestions(profile, candidates, held_tickers, market, universe_by_ticker)

    retrieved_at = datetime.now(timezone.utc).isoformat()
    warnings: list[str] = []
    outside_universe = sum(1 for h in holdings if not h.in_green_canopy_universe)
    if outside_universe:
        warnings.append(
            f"{outside_universe} holding(s) are outside Green Canopy's tracked universe, so they have no "
            "Green Canopy classification tags to match against your priorities."
        )

    portfolio_return = portfolio_volatility = portfolio_drawdown = None
    benchmark = None
    if len(evaluated) >= 2:
        prices = pd.concat([item["history"] for item in evaluated], axis=1, join="inner").dropna()
        if len(prices) >= 60:
            weights = np.array([item["dollar_amount"] / total_value for item in evaluated])
            portfolio_perf = portfolio_metrics(prices, weights)
            portfolio_return = portfolio_perf["annualized_historical_return"]
            portfolio_volatility = portfolio_perf["annualized_volatility"]
            portfolio_drawdown = portfolio_perf["maximum_drawdown"]
            benchmark = benchmark_comparison(market, prices.index)
        else:
            warnings.append("Holdings didn't share enough overlapping price history to compute combined performance.")

    narrative = compose_portfolio_narrative(
        [{"name": h.name, "weight": h.weight, "matched_priorities": h.matched_priorities} for h in holdings],
        dict(sector_totals),
        round(weighted_alignment, 1),
        diversification_score,
    )

    return PortfolioAnalysisResponse(
        investor_profile=profile,
        total_value=round(total_value, 2),
        holdings=holdings,
        sustainability_alignment_score=round(weighted_alignment, 1),
        portfolio_narrative=narrative,
        sector_distribution={key: round(value, 2) for key, value in sector_totals.items()},
        diversification_score=diversification_score,
        annualized_historical_return=portfolio_return,
        annualized_volatility=portfolio_volatility,
        maximum_drawdown=portfolio_drawdown,
        benchmark=benchmark,
        suggestions=suggestions,
        data_retrieved_at=retrieved_at,
        sources=["Yahoo Finance via yfinance", "Green Canopy classification metadata"],
        warnings=warnings,
        limitations=[
            "This reviews your reported holdings only; Green Canopy does not connect to a brokerage.",
            "Green Canopy alignment is a transparent educational score based on classification tags, not a third-party ESG rating.",
            "This educational simulation is not financial advice and does not execute trades.",
        ],
        excluded_holdings=excluded,
    )
