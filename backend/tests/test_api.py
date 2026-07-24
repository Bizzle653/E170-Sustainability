import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import backend.main as main_module


class FakeMarket:
    def get_info(self, symbol):
        return {"longName": f"{symbol} Test Fund", "sector": "Diversified"}

    def get_sustainability(self, symbol):
        return {"totalEsg": 20, "governanceScore": 15}

    def get_history(self, symbol):
        seed = sum(map(ord, symbol))
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2023-01-01", periods=500, freq="B")
        returns = rng.normal(0.0003 + (seed % 5) / 100000, 0.007 + (seed % 3) / 1000, len(dates))
        return pd.Series(100 * np.cumprod(1 + returns), index=dates, name=symbol)


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
    assert max(item["weight"] for item in payload["allocations"]) <= 20.01
    assert any(item["ticker"] in {"XOM", "CVX", "WMB", "XLE"} for item in payload["excluded_investments"])
