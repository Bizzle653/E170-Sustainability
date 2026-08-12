import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import backend.main as main_module
import api.index as vercel_entry
from backend.rate_limit import RATE_LIMITER
from backend.models import CompanyResponse, SustainabilityPayload


class FakeMarket:
    def get_info(self, symbol):
        return {
            "longName": f"{symbol} Test Fund",
            "sector": "Diversified",
            "currentPrice": 125.0,
            "longBusinessSummary": "A test company used to validate the review workflow.",
            "marketCap": 1_000_000,
        }

    def get_sustainability(self, symbol):
        return {"totalEsg": 20, "governanceScore": 15}

    def get_top_holdings(self, symbol):
        return []

    def get_history(self, symbol):
        seed = sum(map(ord, symbol))
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2023-01-01", periods=500, freq="B")
        returns = rng.normal(0.0003 + (seed % 5) / 100000, 0.007 + (seed % 3) / 1000, len(dates))
        return pd.Series(100 * np.cumprod(1 + returns), index=dates, name=symbol)

    def company(self, symbol):
        return CompanyResponse(
            ticker=symbol,
            company_name=f"{symbol} Test Fund",
            sector="Diversified",
            industry="Testing",
            current_price=125.0,
            price_retrieved_at="2026-01-01T00:00:00+00:00",
            annualized_historical_return=0.10,
            annualized_volatility=0.20,
            maximum_drawdown=-0.15,
            yahoo_sustainability=SustainabilityPayload(
                status="available",
                raw_fields=self.get_sustainability(symbol),
                retrieved_at="2026-01-01T00:00:00+00:00",
            ),
            sources=["Yahoo Finance via yfinance"],
            description=self.get_info(symbol)["longBusinessSummary"],
        )

    def sparkline(self, symbol, period="1mo", interval="1d"):
        close = self.get_history(symbol)
        points = [{"date": ts.isoformat(), "close": float(value)} for ts, value in close.tail(20).items()]
        first_price, last_price = points[0]["close"], points[-1]["close"]
        return {
            "ticker": symbol,
            "company_name": f"{symbol} Test Fund",
            "sector": "Diversified",
            "current_price": last_price,
            "change_amount": last_price - first_price,
            "change_percent": (last_price - first_price) / first_price if first_price else 0.0,
            "period": period,
            "interval": interval,
            "points": points,
            "blurb": f"{symbol} Test Fund's closing price over the period shown.",
            "retrieved_at": self._timestamp(),
        }

    def _timestamp(self):
        return "2026-01-01T00:00:00+00:00"


def test_health_and_profile_response_validation():
    client = TestClient(main_module.app)
    assert client.get("/api/health").json() == {"status": "ok", "service": "Green Canopy API"}
    response = client.post("/api/profile", json={"answers": {"priorities": ["climate"], "risk": "stay_invested"}})
    assert response.status_code == 200
    assert response.json()["profile_name"]


def test_vercel_entrypoint_restores_public_api_path():
    client = TestClient(vercel_entry.app)
    response = client.get("/api", params={"_path": "health"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Green Canopy API"}


def test_production_origin_cors_preflight():
    client = TestClient(main_module.app)
    response = client.options(
        "/api/portfolio/generate",
        headers={
            "Origin": "https://e170-sustainability-navy.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://e170-sustainability-navy.vercel.app"


def test_portfolio_api_totals_exclusions_and_schema(monkeypatch):
    monkeypatch.setattr(main_module, "market_data", FakeMarket())
    client = TestClient(main_module.app)
    response = client.post("/api/portfolio/generate", json={
        "investment_amount": 12345.67,
        "number_of_holdings": 8,
        "answers": {
            "priorities": ["climate", "renewable_energy"],
            "risk": "stay_invested",
            "exclusions": ["fossil_fuels"],
            "max_concentration": 0.2
        }
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert round(sum(item["weight"] for item in payload["allocations"]), 2) == 100
    assert round(sum(item["dollar_amount"] for item in payload["allocations"]), 2) == 12345.67
    assert all(item["purchase_price"] > 0 and item["shares"] > 0 for item in payload["allocations"])
    assert max(item["weight"] for item in payload["allocations"]) <= 20.01
    assert any(item["ticker"] in {"XOM", "CVX", "WMB", "XLE"} for item in payload["excluded_investments"])


def test_portfolio_api_respects_asset_preference(monkeypatch):
    monkeypatch.setattr(main_module, "market_data", FakeMarket())
    client = TestClient(main_module.app)
    response = client.post("/api/portfolio/generate", json={
        "investment_amount": 10000,
        "asset_preference": "etfs_only",
        "answers": {"priorities": ["climate"], "risk": "stay_invested"},
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["allocations"]
    assert all(item["asset_type"] == "etf" for item in payload["allocations"])


def test_search_quotes_and_company_review(monkeypatch):
    monkeypatch.setattr(main_module, "market_data", FakeMarket())
    client = TestClient(main_module.app)
    search = client.get("/api/universe/search?q=microsoft")
    assert search.status_code == 200
    assert any(item["ticker"] == "MSFT" for item in search.json()["results"])

    quotes = client.post("/api/portfolio/quotes", json={"tickers": ["MSFT", "MSFT"]})
    assert quotes.status_code == 200
    assert quotes.json()["quotes"] == [{
        "ticker": "MSFT",
        "current_price": 125.0,
        "retrieved_at": "2026-01-01T00:00:00+00:00",
    }]

    generated = client.post("/api/portfolio/generate", json={
        "investment_amount": 10000,
        "answers": {"priorities": ["climate"], "risk": "stay_invested"},
    }).json()
    review = client.post("/api/company/analyze", json={
        "ticker": "MSFT",
        "profile": generated["investor_profile"],
    })
    assert review.status_code == 200, review.text
    assert review.json()["green_canopy_score"] >= 0
    assert review.json()["description"]


def test_market_sparkline_and_watchlist(monkeypatch):
    monkeypatch.setattr(main_module, "market_data", FakeMarket())
    client = TestClient(main_module.app)

    sparkline = client.get("/api/market/sparkline/AAPL")
    assert sparkline.status_code == 200, sparkline.text
    body = sparkline.json()
    assert body["ticker"] == "AAPL"
    assert len(body["points"]) > 0
    assert body["blurb"]

    watchlist = client.get("/api/market/watchlist?tickers=AAPL,MSFT")
    assert watchlist.status_code == 200, watchlist.text
    tickers = [item["ticker"] for item in watchlist.json()["items"]]
    assert tickers == ["AAPL", "MSFT"]

    default_watchlist = client.get("/api/market/watchlist")
    assert default_watchlist.status_code == 200
    assert len(default_watchlist.json()["items"]) == len(main_module.DEFAULT_WATCHLIST)


def test_classification_announcement_and_security_endpoints(monkeypatch):
    update = {
        "id": "update-1",
        "ticker": "MSFT",
        "name": "Microsoft",
        "asset_type": "stock",
        "published_at": "2026-08-11T00:00:00+00:00",
        "agent": "Green Canopy Sustainability Intelligence Agent",
        "model": "deepseek-chat",
        "old_tags": [],
        "new_tags": ["climate"],
        "added_tags": ["climate"],
        "removed_tags": [],
        "old_exclusions": [],
        "new_exclusions": [],
        "added_exclusions": [],
        "removed_exclusions": [],
        "summary": "Evidence-backed update.",
        "confidence": 0.9,
        "accepted_assessments": [],
        "evidence": [],
        "greenwashing_flags": [],
        "portfolio_impact": "Scores may change; allocations do not.",
    }
    monkeypatch.setattr(
        main_module,
        "load_classification_updates",
        lambda limit=50, offset=0, ticker=None: {
            "schema_version": 1,
            "total": 1,
            "offset": offset,
            "next_offset": None,
            "updates": [update],
        },
    )
    monkeypatch.setattr(
        main_module,
        "load_security_classification",
        lambda ticker: {
            "universe_version": "2026-08-11",
            "ticker": ticker.upper(),
            "name": "Microsoft",
            "asset_type": "stock",
            "tags": ["climate"],
            "exclusions": [],
            "classification": {"confidence": 0.9},
            "history": [update],
        },
    )
    client = TestClient(main_module.app)

    announcements = client.get("/api/classifications/updates")
    assert announcements.status_code == 200
    assert announcements.json()["updates"][0]["added_tags"] == ["climate"]

    classification = client.get("/api/classifications/msft")
    assert classification.status_code == 200
    assert classification.json()["ticker"] == "MSFT"


def test_agent_status_endpoint():
    client = TestClient(main_module.app)
    response = client.get("/api/agent/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_securities"] == 1055
    assert payload["verified_securities"] >= 1
    assert payload["policy_version"]


def test_chat_endpoint_has_cost_rate_limit(monkeypatch):
    RATE_LIMITER.clear()
    monkeypatch.setattr(main_module, "run_agent", lambda message: f"Reply to {message}")
    client = TestClient(main_module.app)
    headers = {"x-forwarded-for": "203.0.113.10"}
    for _ in range(12):
        assert client.post("/api/chat", json={"message": "hello"}, headers=headers).status_code == 200
    limited = client.post("/api/chat", json={"message": "hello"}, headers=headers)
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0
    RATE_LIMITER.clear()
