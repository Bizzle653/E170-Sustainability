from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.models import CompanyResponse, InvestorProfile, PortfolioRequest, PortfolioResponse, ProfileRequest
from backend.services.investor_profile import build_profile
from backend.services.market_data import MarketDataError, MarketDataService
from backend.services.portfolio import generate_portfolio, load_universe


app = FastAPI(
    title="Green Canopy API",
    version="0.1.0",
    description="Educational sustainable-investing portfolio simulation.",
)

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://e170-sustaniability-dogi.vercel.app",
]
configured_origins = [
    origin.strip()
    for origin in os.getenv("GREEN_CANOPY_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(default_origins + configured_origins)),
    allow_methods=["*"],
    allow_headers=["*"],
)
market_data = MarketDataService()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Green Canopy API"}


@app.get("/api/universe")
def universe() -> dict[str, object]:
    data = load_universe()
    securities = data["securities"]
    return {
        "version": data["version"],
        "scope": data["scope"],
        "counts": {
            "companies": sum(item["type"] == "stock" for item in securities),
            "etfs": sum(item["type"] == "etf" for item in securities),
        },
    }


@app.get("/api/company/{ticker}", response_model=CompanyResponse)
def company(ticker: str) -> CompanyResponse:
    try:
        return market_data.company(ticker)
    except MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/profile", response_model=InvestorProfile)
def profile(request: ProfileRequest) -> InvestorProfile:
    return build_profile(request.answers)


@app.post("/api/portfolio/generate", response_model=PortfolioResponse)
def portfolio(request: PortfolioRequest) -> PortfolioResponse:
    try:
        return generate_portfolio(request, market_data)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
