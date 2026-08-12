from __future__ import annotations

import math
import re
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


_ABBREVIATIONS = {"inc", "corp", "co", "ltd", "llc", "plc", "l.p", "s.a", "n.v", "jr", "sr", "e.g", "i.e"}


def split_sentences(text: str | None) -> list[str]:
    """Split a business summary into abbreviation-aware sentences."""
    if not text:
        return []
    text = text.strip()
    if not text:
        return []
    sentences: list[str] = []
    start = 0
    for match in re.finditer(r"\.(\s+|$)", text):
        end = match.start()
        preceding_word = re.split(r"[\s,(]", text[:end])[-1].lower()
        if preceding_word in _ABBREVIATIONS:
            continue
        sentences.append(text[start : end + 1].strip())
        start = match.end()
    if start < len(text):
        sentences.append(text[start:].strip())
    return [s for s in sentences if s]


def first_sentence(text: str | None, max_length: int = 220) -> str | None:
    """Extract a single readable sentence from a longer business summary."""
    sentences = split_sentences(text)
    if not sentences:
        return None
    sentence = sentences[0]
    return sentence if len(sentence) <= max_length else sentence[:max_length].rsplit(" ", 1)[0] + "…"


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
    SUPPORTED_HISTORY_PERIODS = frozenset({
        "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "10y", "ytd", "max",
    })
    SUPPORTED_HISTORY_INTERVALS = frozenset({
        "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo",
    })

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
        history = self.get_history_frame(symbol, period="3y", interval="1d")
        close = pd.to_numeric(history["Close"], errors="coerce").dropna()
        if len(close) < 60:
            raise MarketDataError(f"Insufficient price history for {symbol}")
        close.name = symbol
        return close

    def get_history_frame(self, symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
        """Return an auto-adjusted yfinance history frame for an approved range."""
        symbol = symbol.upper().strip()
        period = period.lower().strip()
        interval = interval.lower().strip()
        if period not in self.SUPPORTED_HISTORY_PERIODS:
            raise MarketDataError(f"Unsupported history period: {period}")
        if interval not in self.SUPPORTED_HISTORY_INTERVALS:
            raise MarketDataError(f"Unsupported history interval: {interval}")

        def load() -> pd.DataFrame:
            try:
                history = self._ticker(symbol).history(
                    period=period,
                    interval=interval,
                    auto_adjust=True,
                )
            except Exception as exc:
                raise MarketDataError(f"Price history unavailable for {symbol}: {exc}") from exc
            if history is None or history.empty or "Close" not in history:
                raise MarketDataError(f"Price history is empty for {symbol}")
            return history.copy()

        intraday = interval.endswith("m") or interval.endswith("h")
        ttl = self.INFO_TTL if intraday else self.HISTORY_TTL
        cache_key = f"history-frame:{symbol}:{period}:{interval}"
        return self.cache.get_or_set(cache_key, ttl, load)

    def sparkline(self, symbol: str, period: str = "1mo", interval: str = "1d") -> dict[str, Any]:
        """Build a chart-ready price series plus a plain-English blurb for one ticker."""
        symbol = symbol.upper().strip()
        frame = self.get_history_frame(symbol, period=period, interval=interval)
        close = pd.to_numeric(frame["Close"], errors="coerce").dropna()
        if close.empty:
            raise MarketDataError(f"No price history for {symbol}")
        info = self.get_info(symbol)

        points = [{"date": timestamp.isoformat(), "close": float(value)} for timestamp, value in close.items()]
        if len(points) > 150:
            step = math.ceil(len(points) / 150)
            sampled = points[::step]
            if sampled[-1] is not points[-1]:
                sampled.append(points[-1])
            points = sampled

        first_price = float(close.iloc[0])
        last_price = float(close.iloc[-1])
        name = info.get("longName") or info.get("shortName") or symbol
        blurb = first_sentence(info.get("longBusinessSummary")) or f"{name}'s closing price over the period shown."

        return {
            "ticker": symbol,
            "company_name": name,
            "sector": info.get("sector"),
            "current_price": last_price,
            "change_amount": last_price - first_price,
            "change_percent": (last_price - first_price) / first_price if first_price else 0.0,
            "period": period,
            "interval": interval,
            "points": points,
            "blurb": blurb,
            "retrieved_at": self._timestamp(),
        }

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

    def get_top_holdings(self, symbol: str, limit: int = 8) -> list[dict[str, Any]]:
        """Fetch a fund's actual current holdings (real companies, not legal text)."""
        symbol = symbol.upper().strip()

        def load() -> list[dict[str, Any]]:
            try:
                funds_data = self._ticker(symbol).funds_data
                holdings = funds_data.top_holdings if funds_data is not None else None
            except Exception:
                return []
            if holdings is None or holdings.empty:
                return []
            results = []
            for ticker_symbol, row in holdings.iterrows():
                results.append({
                    "ticker": str(ticker_symbol),
                    "name": str(row.get("Name", ticker_symbol)),
                    "weight": _json_value(row.get("Holding Percent")),
                })
            return results[:limit]

        return self.cache.get_or_set(f"holdings:{symbol}", self.SUSTAINABILITY_TTL, load)

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
            description=info.get("longBusinessSummary"),
        )


def _json_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value
