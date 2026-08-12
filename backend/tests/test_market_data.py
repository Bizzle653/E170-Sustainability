import numpy as np
import pandas as pd
import pytest

from backend.services.market_data import MarketDataError, MarketDataService


class FakeTicker:
    def __init__(self, symbol: str, sustainability: bool = True, empty: bool = False):
        self.symbol = symbol
        self.has_sustainability = sustainability
        self.empty = empty

    def get_info(self):
        return {"longName": "Example Corp", "sector": "Technology", "industry": "Software", "currentPrice": 123.45}

    def history(self, **kwargs):
        if self.empty:
            return pd.DataFrame()
        dates = pd.date_range("2023-01-01", periods=500, freq="B")
        return pd.DataFrame({"Close": np.linspace(80, 130, len(dates))}, index=dates)

    def get_sustainability(self):
        if not self.has_sustainability:
            return None
        return pd.DataFrame({"Value": [18.0, 2]}, index=["totalEsg", "controversyLevel"])


def test_company_with_complete_market_and_sustainability():
    service = MarketDataService(lambda symbol: FakeTicker(symbol))
    result = service.company("TEST")
    assert result.company_name == "Example Corp"
    assert result.yahoo_sustainability.status == "available"
    assert result.yahoo_sustainability.raw_fields["totalEsg"] == 18.0
    assert result.annualized_volatility >= 0


def test_missing_sustainability_is_null_status_not_fabricated_score():
    service = MarketDataService(lambda symbol: FakeTicker(symbol, sustainability=False))
    result = service.company("TEST")
    assert result.yahoo_sustainability.status == "unavailable"
    assert result.yahoo_sustainability.raw_fields == {}


def test_empty_price_history_raises_visible_error():
    service = MarketDataService(lambda symbol: FakeTicker(symbol, empty=True))
    with pytest.raises(MarketDataError, match="empty"):
        service.company("TEST")


def test_history_frame_rejects_unsupported_ranges_before_fetching():
    service = MarketDataService(lambda symbol: FakeTicker(symbol))
    with pytest.raises(MarketDataError, match="period"):
        service.get_history_frame("TEST", period="forever", interval="1d")
    with pytest.raises(MarketDataError, match="interval"):
        service.get_history_frame("TEST", period="1mo", interval="4h")


def test_sparkline_returns_points_change_and_blurb():
    service = MarketDataService(lambda symbol: FakeTicker(symbol))
    result = service.sparkline("TEST", period="1mo", interval="1d")
    assert result["ticker"] == "TEST"
    assert len(result["points"]) <= 150
    assert result["points"][0]["close"] < result["points"][-1]["close"]
    assert result["change_amount"] > 0
    assert result["change_percent"] > 0
    assert result["blurb"]


def test_sparkline_downsamples_long_histories():
    service = MarketDataService(lambda symbol: FakeTicker(symbol))
    result = service.sparkline("TEST", period="2y", interval="1d")
    assert len(result["points"]) <= 150
    assert result["points"][-1]["close"] > 0


def test_sparkline_raises_on_empty_history():
    service = MarketDataService(lambda symbol: FakeTicker(symbol, empty=True))
    with pytest.raises(MarketDataError):
        service.sparkline("TEST")
