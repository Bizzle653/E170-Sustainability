import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import backend.main as main_module
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
        )

    def _timestamp(self):
        return "2026-01-01T00:00:00+00:00"


def test_health_and_profile_response_validation():
    client = TestClient(main_module.app)
    assert client.get("/api/health").json() == {"status": "ok", "service": "Green Canopy API"}
    response = client.post("/api/profile", json={"answers": {"priorities": ["climate"], "risk": "stay_invested"}})
    assert response.status_code == 200
    assert response.json()["profile_name"]


def test_production_origin_cors_preflight():
    client = TestClient(main_module.app)
    response = client.options(
        "/api/portfolio/generate",
        headers={
            "Origin": "https://e170-sustaniability-dogi.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://e170-sustaniability-dogi.vercel.app"


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
