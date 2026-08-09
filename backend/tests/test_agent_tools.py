import json

import numpy as np
import pandas as pd
import pytest

from backend.agent_tools import TOOL_DEFINITIONS, execute_tool
from backend.services.market_data import MarketDataError


class FakeAgentMarketData:
    def get_info(self, symbol):
        return {
            "longName": "Example Corp",
            "currency": "USD",
            "fullExchangeName": "NasdaqGS",
            "quoteType": "EQUITY",
            "currentPrice": 123.45,
            "previousClose": 120.0,
            "marketCap": np.int64(1_000_000),
            "sector": "Technology",
            "industry": "Software",
            "longBusinessSummary": "Example business description.",
        }

    def get_history_frame(self, symbol, period, interval):
        dates = pd.date_range("2026-07-01", periods=5, freq="B", tz="UTC")
        return pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104],
                "High": [102, 103, 104, 105, 106],
                "Low": [99, 100, 101, 102, 103],
                "Close": [101, 102, 103, 104, 105],
                "Volume": np.array([10, 20, 30, 40, 50], dtype=np.int64),
                "Dividends": [0.0, 0.0, 0.25, 0.0, np.nan],
            },
            index=dates,
        )

    def get_top_holdings(self, symbol, limit):
        return [{"ticker": "MSFT", "name": "Microsoft", "weight": 0.08}][:limit]


def test_yfinance_tool_is_registered():
    names = {definition["function"]["name"] for definition in TOOL_DEFINITIONS}
    assert "get_yfinance_data" in names


def test_yfinance_quote_returns_curated_serialisable_data():
    payload = json.loads(execute_tool(
        "get_yfinance_data",
        {"ticker": "test", "data_type": "quote"},
        market_data=FakeAgentMarketData(),
    ))
    assert payload["ticker"] == "TEST"
    assert payload["quote"]["current_price"] == 123.45
    assert payload["quote"]["market_cap"] == 1_000_000
    assert payload["source"] == "Yahoo Finance via yfinance"
    assert payload["retrieved_at"]


def test_yfinance_history_is_limited_and_json_safe():
    payload = json.loads(execute_tool(
        "get_yfinance_data",
        {
            "ticker": "TEST",
            "data_type": "price_history",
            "period": "1mo",
            "interval": "1d",
            "limit": 2,
        },
        market_data=FakeAgentMarketData(),
    ))
    assert payload["rows_available"] == 5
    assert payload["rows_returned"] == 2
    assert payload["history"][0]["close"] == 104
    assert payload["history"][1]["dividends"] is None
    assert payload["summary"]["period_return"] == pytest.approx(105 / 101 - 1)


def test_yfinance_tool_rejects_invalid_ticker_before_lookup():
    with pytest.raises(MarketDataError, match="Invalid"):
        execute_tool(
            "get_yfinance_data",
            {"ticker": "bad ticker", "data_type": "quote"},
            market_data=FakeAgentMarketData(),
        )
