from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import pandas as pd
import yfinance as yf

from backend.models import CompanyResponse, SustainabilityPayload


class MarketDataError(RuntimeError):
    pass


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._items: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: str, ttl: int, loader: Callable[[], Any]) -> Any:
        now = time.time()
        with self._lock:
            entry = self._items.get(key)
            if entry and entry.expires_at > now:
                return entry.value
        value = loader()
        with self._lock:
            self._items[key] = CacheEntry(value, now + ttl)
        return value


class MarketDataService:
    INFO_TTL = 15 * 60
    HISTORY_TTL = 12 * 60 * 60
    SUSTAINABILITY_TTL = 24 * 60 * 60

    def __init__(self, ticker_factory: Callable[[str], Any] = yf.Ticker) -> None:
        self.ticker_factory = ticker_factory
        self.cache = TTLCache()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ticker(self, symbol: str) -> Any:
        return self.ticker_factory(symbol)

    def get_info(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper().strip()

        def load() -> dict[str, Any]:
            ticker = self._ticker(symbol)
            try:
                info = ticker.get_info()
            except Exception as exc:
                raise MarketDataError(f"Company information unavailable for {symbol}: {exc}") from exc
            return dict(info or {})

        return self.cache.get_or_set(f"info:{symbol}", self.INFO_TTL, load)

    def get_history(self, symbol: str) -> pd.Series:
        symbol = symbol.upper().strip()

        def load() -> pd.Series:
            try:
                history = self._ticker(symbol).history(period="3y", interval="1d", auto_adjust=True)
            except Exception as exc:
                raise MarketDataError(f"Price history unavailable for {symbol}: {exc}") from exc
            if history is None or history.empty or "Close" not in history:
                raise MarketDataError(f"Price history is empty for {symbol}")
            close = pd.to_numeric(history["Close"], errors="coerce").dropna()
            if len(close) < 60:
                raise MarketDataError(f"Insufficient price history for {symbol}")
            close.name = symbol
            return close

        return self.cache.get_or_set(f"history:{symbol}", self.HISTORY_TTL, load)

    def get_sustainability(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper().strip()

        def load() -> dict[str, Any]:
            try:
                ticker = self._ticker(symbol)
                result = ticker.get_sustainability() if hasattr(ticker, "get_sustainability") else ticker.sustainability
            except Exception:
                return {}
            if result is None:
                return {}
            if isinstance(result, pd.DataFrame):
                if result.empty:
                    return {}
                if "Value" in result.columns:
                    series = result["Value"]
                elif result.shape[1] == 1:
                    series = result.iloc[:, 0]
                else:
                    return {}
                return {str(key): _json_value(value) for key, value in series.items()}
            if isinstance(result, dict):
                return {str(key): _json_value(value) for key, value in result.items()}
            return {}

        return self.cache.get_or_set(f"sustainability:{symbol}", self.SUSTAINABILITY_TTL, load)

    @staticmethod
    def metrics(close: pd.Series) -> dict[str, float]:
        returns = close.pct_change().dropna()
        if returns.empty:
            raise MarketDataError("Unable to calculate returns")
        annual_return = float((1 + returns.mean()) ** 252 - 1)
        volatility = float(returns.std(ddof=1) * math.sqrt(252))
        drawdown = close / close.cummax() - 1
        return {
            "annualized_historical_return": annual_return,
            "annualized_volatility": volatility,
            "maximum_drawdown": float(drawdown.min()),
        }

    def company(self, symbol: str) -> CompanyResponse:
        symbol = symbol.upper().strip()
        if not symbol or len(symbol) > 10:
            raise MarketDataError("Invalid ticker symbol")
        retrieved_at = self._timestamp()
        info = self.get_info(symbol)
        close = self.get_history(symbol)
        sustainability = self.get_sustainability(symbol)
        metrics = self.metrics(close)
        price = info.get("currentPrice") or info.get("regularMarketPrice") or float(close.iloc[-1])
        rating_date = sustainability.get("ratingYear") or sustainability.get("ratingMonth")
        return CompanyResponse(
            ticker=symbol,
            company_name=info.get("longName") or info.get("shortName") or symbol,
            sector=info.get("sector"),
            industry=info.get("industry"),
            current_price=float(price),
            price_retrieved_at=retrieved_at,
            **metrics,
            yahoo_sustainability=SustainabilityPayload(
                status="available" if sustainability else "unavailable",
                raw_fields=sustainability,
                retrieved_at=retrieved_at,
                rating_date=str(rating_date) if rating_date is not None else None,
            ),
            sources=["Yahoo Finance via yfinance"],
        )


def _json_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value
