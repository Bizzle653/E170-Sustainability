"""
Agent Tool Schemas for Green Canopy business functions.

Wraps core portfolio and sustainability services as OpenAI/DeepSeek-compatible
function-calling Tool Schemas. Each tool definition includes a JSON Schema for
its parameters, and each handler function accepts the parsed arguments, calls
the underlying service, and returns a serialisable result.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from backend.models import InvestorProfile, QuestionnaireAnswers
from backend.services.investor_profile import build_profile as _build_profile
from backend.services.portfolio_optimizer import (
    optimize_weights as _optimize_weights,
    portfolio_metrics as _portfolio_metrics,
    rounded_allocations as _rounded_allocations,
)
from backend.services.market_data import MarketDataError, MarketDataService
from backend.services.sustainability import (
    alignment_score as _alignment_score,
    compose_fund_snapshot as _compose_fund_snapshot,
    compose_portfolio_narrative as _compose_portfolio_narrative,
)

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI / DeepSeek function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "build_investor_profile",
            "description": (
                "Build a deterministic investor profile from questionnaire answers. "
                "Computes a risk score (0-100), assigns a profile name, and calculates "
                "sustainability priority weights from the user's ranked priorities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "priorities": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "climate",
                                "renewable_energy",
                                "fair_labor",
                                "human_rights",
                                "biodiversity",
                                "clean_water",
                                "sustainable_agriculture",
                                "circular_economy",
                                "governance",
                            ],
                        },
                        "description": "Ordered list of sustainability priorities (most important first).",
                    },
                    "goal": {
                        "type": "string",
                        "enum": ["long_term_growth", "growth_and_stability", "income_and_preservation"],
                        "description": "Investment objective.",
                    },
                    "horizon": {
                        "type": "string",
                        "enum": ["under_3_years", "3_to_10_years", "10_plus_years"],
                        "description": "Investment time horizon.",
                    },
                    "risk": {
                        "type": "string",
                        "enum": ["move_to_safety", "stay_invested", "invest_more"],
                        "description": "Risk posture during a market decline.",
                    },
                    "decline_reaction": {
                        "type": "string",
                        "enum": ["sell", "hold", "buy_more"],
                        "description": "Reaction to a 20% portfolio decline.",
                    },
                    "philosophy": {
                        "type": "string",
                        "enum": ["avoid_harm", "fund_solutions", "combination"],
                        "description": "Company selection philosophy.",
                    },
                    "tradeoff": {
                        "type": "string",
                        "enum": ["none", "small", "moderate", "strong"],
                        "description": "Willingness to trade financial return for sustainability.",
                    },
                    "exclusions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Categories or tickers to exclude.",
                    },
                    "max_concentration": {
                        "type": "number",
                        "description": "Maximum allocation per holding (0.10-0.20).",
                    },
                },
                "required": ["priorities", "goal", "horizon", "risk", "decline_reaction", "philosophy", "tradeoff"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_alignment_score",
            "description": (
                "Calculate a sustainability alignment score for a single holding. "
                "Combines the investor's priority weights with the company's Green Canopy "
                "classification tags and (if available) third-party ESG data to produce "
                "a 0-100 alignment score with confidence level."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_json": {
                        "type": "string",
                        "description": "JSON-serialised InvestorProfile object.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Green Canopy classification tags for the holding.",
                    },
                    "asset_type": {
                        "type": "string",
                        "enum": ["stock", "etf"],
                        "description": "Type of the security.",
                    },
                    "business_summary": {
                        "type": "string",
                        "description": "Optional business description text from the company.",
                    },
                },
                "required": ["profile_json", "tags", "asset_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_portfolio_weights",
            "description": (
                "Run a constrained mean-variance optimisation that balances expected return, "
                "volatility, sustainability alignment, and income tilt. Returns an array of "
                "portfolio weights summing to 1."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_json": {
                        "type": "string",
                        "description": "JSON-serialised InvestorProfile object.",
                    },
                    "alignment_scores": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Alignment scores (0-100) for each candidate, same order as returns/covariance.",
                    },
                    "income_ranks": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Dividend-yield percentile ranks (0-1) for each candidate.",
                    },
                    "max_weight": {
                        "type": "number",
                        "description": "Maximum allowed weight per holding (e.g. 0.20).",
                    },
                    "num_assets": {
                        "type": "integer",
                        "description": "Number of assets in the optimisation.",
                    },
                },
                "required": ["profile_json", "alignment_scores", "income_ranks", "max_weight", "num_assets"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_portfolio_metrics",
            "description": (
                "Compute annualised historical return, annualised volatility, and maximum "
                "drawdown for a portfolio given historical prices and weights."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "num_assets": {
                        "type": "integer",
                        "description": "Number of assets (used for validation).",
                    },
                },
                "required": ["num_assets"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rounded_allocations",
            "description": (
                "Convert fractional portfolio weights into rounded percentage and dollar "
                "allocations for a given total investment amount."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "weights_json": {
                        "type": "string",
                        "description": "JSON-encoded list of portfolio weights.",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Total investment amount in dollars.",
                    },
                },
                "required": ["weights_json", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compose_portfolio_narrative",
            "description": (
                "Generate a human-readable, data-driven paragraph summarising a portfolio: "
                "top sectors, anchor holdings, priority coverage, alignment level, and "
                "diversification score. Built entirely from computed data — no language model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "holdings_json": {
                        "type": "string",
                        "description": (
                            "JSON-encoded list of holding dicts, each with keys: "
                            "name, weight, matched_priorities."
                        ),
                    },
                    "sector_totals_json": {
                        "type": "string",
                        "description": "JSON-encoded dict of sector -> total weight.",
                    },
                    "weighted_alignment": {
                        "type": "number",
                        "description": "Portfolio-level weighted alignment score (0-100).",
                    },
                    "diversification_score": {
                        "type": "number",
                        "description": "Portfolio diversification score (0-100).",
                    },
                },
                "required": [
                    "holdings_json",
                    "sector_totals_json",
                    "weighted_alignment",
                    "diversification_score",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compose_fund_snapshot",
            "description": (
                "Create a short, prioritised snapshot of a fund by cross-referencing its "
                "real top holdings against the user's sustainability priorities and "
                "Green Canopy's classification tags."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "top_holdings_json": {
                        "type": "string",
                        "description": (
                            "JSON-encoded list of top holding dicts, each with keys: "
                            "ticker, name, weight."
                        ),
                    },
                    "universe_by_ticker_json": {
                        "type": "string",
                        "description": (
                            "JSON-encoded dict mapping ticker -> universe entry (must include 'tags' key)."
                        ),
                    },
                    "active_priorities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of priority keys the user selected.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of holdings to include in the snapshot (default 3).",
                    },
                },
                "required": ["top_holdings_json", "active_priorities"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_yfinance_data",
            "description": (
                "Retrieve current public market data from Yahoo Finance through yfinance. "
                "Use it for quotes, company or fund profiles, auto-adjusted OHLCV price "
                "history, and ETF or mutual-fund top holdings. Never invent values if the "
                "tool reports that data is unavailable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Yahoo Finance ticker, for example MSFT, VTI, ^GSPC, or BTC-USD.",
                    },
                    "data_type": {
                        "type": "string",
                        "enum": ["quote", "company_profile", "price_history", "fund_holdings"],
                        "description": "The category of yfinance data to retrieve.",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "10y", "ytd", "max"],
                        "description": "History lookback. Used only for price_history; defaults to 1mo.",
                    },
                    "interval": {
                        "type": "string",
                        "enum": ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"],
                        "description": "History sampling interval. Used only for price_history; defaults to 1d.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Maximum history rows (100) or fund holdings (25) returned.",
                    },
                },
                "required": ["ticker", "data_type"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool handler (dispatches function name → implementation)
# ---------------------------------------------------------------------------

_MARKET_DATA = MarketDataService()


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    market_data: MarketDataService | None = None,
) -> str:
    """Execute a tool by name with the given arguments and return a JSON string result."""

    if name == "build_investor_profile":
        answers = QuestionnaireAnswers(
            priorities=arguments.get("priorities", ["climate"]),
            goal=arguments.get("goal", "growth_and_stability"),
            horizon=arguments.get("horizon", "10_plus_years"),
            risk=arguments.get("risk", "stay_invested"),
            decline_reaction=arguments.get("decline_reaction", "hold"),
            philosophy=arguments.get("philosophy", "combination"),
            tradeoff=arguments.get("tradeoff", "small"),
            exclusions=arguments.get("exclusions", []),
            max_concentration=arguments.get("max_concentration", 0.20),
        )
        profile: InvestorProfile = _build_profile(answers)
        return profile.model_dump_json(indent=2)

    if name == "calculate_alignment_score":
        profile = InvestorProfile.model_validate_json(arguments["profile_json"])
        result = _alignment_score(
            profile=profile,
            tags=arguments.get("tags", []),
            raw=None,
            asset_type=arguments.get("asset_type", "stock"),
            business_summary=arguments.get("business_summary"),
            fund_evidence=None,
        )
        return json.dumps(result, default=_serialise, indent=2)

    if name == "optimize_portfolio_weights":
        profile = InvestorProfile.model_validate_json(arguments["profile_json"])
        n = arguments["num_assets"]
        alignment = arguments.get("alignment_scores", [50.0] * n)
        income = arguments.get("income_ranks", [0.5] * n)
        # Create synthetic price data for the optimisation call (the real call
        # requires a pd.DataFrame of historical prices; for agent-driven use we
        # accept that the agent provides pre-computed alignments and the caller
        # must stage the price dataframe externally).
        return json.dumps(
            {
                "status": "requires_prices_dataframe",
                "message": (
                    "optimize_weights requires a pandas DataFrame of historical prices "
                    "and is designed to be called from the FastAPI layer with live market data. "
                    "The agent can guide the user to use the /api/portfolio/generate endpoint "
                    "which orchestrates data retrieval and optimisation together."
                ),
            },
            indent=2,
        )

    if name == "calculate_portfolio_metrics":
        return json.dumps(
            {
                "status": "requires_prices_dataframe",
                "message": (
                    "portfolio_metrics requires a pandas DataFrame of historical prices "
                    "and is designed to be called from the FastAPI layer with live market data. "
                    "The agent can guide the user to use the /api/portfolio/generate endpoint "
                    "which computes these metrics automatically."
                ),
            },
            indent=2,
        )

    if name == "rounded_allocations":
        weights = json.loads(arguments["weights_json"])
        amount = float(arguments["amount"])
        percentages, dollars = _rounded_allocations(np.array(weights, dtype=float), amount)
        return json.dumps(
            {"percentages": percentages, "dollars": dollars},
            indent=2,
        )

    if name == "compose_portfolio_narrative":
        holdings = json.loads(arguments["holdings_json"])
        sector_totals = json.loads(arguments["sector_totals_json"])
        narrative = _compose_portfolio_narrative(
            holdings=holdings,
            sector_totals=sector_totals,
            weighted_alignment=float(arguments["weighted_alignment"]),
            diversification_score=float(arguments["diversification_score"]),
        )
        return json.dumps({"narrative": narrative}, indent=2)

    if name == "compose_fund_snapshot":
        top_holdings = json.loads(arguments["top_holdings_json"])
        universe = json.loads(arguments.get("universe_by_ticker_json", "{}"))
        active = arguments.get("active_priorities", [])
        limit = arguments.get("limit", 3)
        snapshot, evidence = _compose_fund_snapshot(
            top_holdings=top_holdings,
            universe_by_ticker=universe,
            active_priorities=active,
            limit=limit,
        )
        return json.dumps(
            {"snapshot": snapshot, "evidence": evidence},
            indent=2,
        )

    if name == "get_yfinance_data":
        result = _get_yfinance_data(arguments, market_data or _MARKET_DATA)
        return json.dumps(result, default=_serialise, allow_nan=False, indent=2)

    return json.dumps({"error": f"Unknown tool: {name}"})


def _get_yfinance_data(arguments: dict[str, Any], market_data: MarketDataService) -> dict[str, Any]:
    ticker = str(arguments.get("ticker", "")).upper().strip()
    if not re.fullmatch(r"[A-Z0-9.^=\-]{1,20}", ticker):
        raise MarketDataError("Invalid Yahoo Finance ticker symbol")

    data_type = str(arguments.get("data_type", "")).lower().strip()
    supported_types = {"quote", "company_profile", "price_history", "fund_holdings"}
    if data_type not in supported_types:
        raise MarketDataError(f"Unsupported yfinance data type: {data_type or 'missing'}")

    base: dict[str, Any] = {
        "ticker": ticker,
        "data_type": data_type,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance",
    }

    if data_type in {"quote", "company_profile"}:
        info = market_data.get_info(ticker)
        if not info:
            raise MarketDataError(f"Yahoo Finance returned no information for {ticker}")
        if data_type == "quote":
            quote_fields = {
                "company_name": ("longName", "shortName"),
                "currency": ("currency",),
                "exchange": ("fullExchangeName", "exchange"),
                "quote_type": ("quoteType",),
                "current_price": ("currentPrice", "regularMarketPrice", "navPrice"),
                "previous_close": ("previousClose", "regularMarketPreviousClose"),
                "market_open": ("open", "regularMarketOpen"),
                "day_low": ("dayLow", "regularMarketDayLow"),
                "day_high": ("dayHigh", "regularMarketDayHigh"),
                "fifty_two_week_low": ("fiftyTwoWeekLow",),
                "fifty_two_week_high": ("fiftyTwoWeekHigh",),
                "volume": ("volume", "regularMarketVolume"),
                "average_volume": ("averageVolume",),
                "market_cap": ("marketCap",),
            }
            base["quote"] = {
                output_key: _first_info_value(info, source_keys)
                for output_key, source_keys in quote_fields.items()
            }
            return base

        profile_fields = {
            "company_name": ("longName", "shortName"),
            "quote_type": ("quoteType",),
            "sector": ("sector",),
            "industry": ("industry",),
            "country": ("country",),
            "website": ("website",),
            "currency": ("currency",),
            "exchange": ("fullExchangeName", "exchange"),
            "market_cap": ("marketCap",),
            "trailing_pe": ("trailingPE",),
            "forward_pe": ("forwardPE",),
            "price_to_book": ("priceToBook",),
            "dividend_yield": ("dividendYield",),
            "beta": ("beta",),
            "employees": ("fullTimeEmployees",),
            "business_summary": ("longBusinessSummary",),
        }
        profile = {
            output_key: _first_info_value(info, source_keys)
            for output_key, source_keys in profile_fields.items()
        }
        summary = profile.get("business_summary")
        if isinstance(summary, str) and len(summary) > 2_000:
            profile["business_summary"] = summary[:1_997].rstrip() + "..."
        base["company_profile"] = profile
        return base

    if data_type == "price_history":
        period = str(arguments.get("period", "1mo")).lower().strip()
        interval = str(arguments.get("interval", "1d")).lower().strip()
        limit = _bounded_int(arguments.get("limit", 30), minimum=1, maximum=100)
        history = market_data.get_history_frame(ticker, period=period, interval=interval)
        close = pd.to_numeric(history["Close"], errors="coerce").dropna()
        if close.empty:
            raise MarketDataError(f"Yahoo Finance returned no closing prices for {ticker}")

        records: list[dict[str, Any]] = []
        column_map = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Dividends": "dividends",
            "Stock Splits": "stock_splits",
        }
        for index, row in history.tail(limit).iterrows():
            record: dict[str, Any] = {"date": _clean_market_value(index)}
            for source_column, output_key in column_map.items():
                if source_column in history.columns:
                    record[output_key] = _clean_market_value(row[source_column])
            records.append(record)

        high = pd.to_numeric(history["High"], errors="coerce").dropna() if "High" in history else close
        low = pd.to_numeric(history["Low"], errors="coerce").dropna() if "Low" in history else close
        base.update({
            "period": period,
            "interval": interval,
            "auto_adjusted": True,
            "rows_available": int(len(history)),
            "rows_returned": len(records),
            "summary": {
                "first_close": float(close.iloc[0]),
                "last_close": float(close.iloc[-1]),
                "period_return": float(close.iloc[-1] / close.iloc[0] - 1) if len(close) > 1 else None,
                "period_high": float(high.max()),
                "period_low": float(low.min()),
            },
            "history": records,
        })
        return base

    limit = _bounded_int(arguments.get("limit", 10), minimum=1, maximum=25)
    holdings = market_data.get_top_holdings(ticker, limit=limit)
    base["top_holdings"] = holdings
    base["holdings_available"] = bool(holdings)
    if not holdings:
        base["message"] = "Yahoo Finance did not provide fund holdings for this ticker."
    return base


def _first_info_value(info: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = _clean_market_value(info.get(key))
        if value is not None:
            return value
    return None


def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataError("limit must be an integer") from exc
    return max(minimum, min(maximum, parsed))


def _clean_market_value(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (float, np.floating)) and np.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _serialise(obj: Any) -> Any:
    """Fallback JSON serialiser for market-data and numpy types."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")
