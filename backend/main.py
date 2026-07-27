from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.models import (
    CompanyAnalysisRequest,
    CompanyAnalysisResponse,
    CompanyResponse,
    InvestorProfile,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    PortfolioRequest,
    PortfolioResponse,
    ProfileRequest,
    QuoteItem,
    QuoteRequest,
    QuoteResponse,
)
from backend.services.investor_profile import build_profile
from backend.services.market_data import MarketDataError, MarketDataService
from backend.services.portfolio import generate_portfolio, load_universe
from backend.services.portfolio_review import analyze_portfolio
from backend.services.sustainability import alignment_score


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


@app.get("/api/universe/search")
def search_universe(q: str = "", limit: int = 10) -> dict[str, object]:
    query = q.strip().lower()
    if len(query) < 1:
        return {"results": []}
    limit = max(1, min(limit, 20))
    results = []
    for item in load_universe()["securities"]:
        if item["type"] != "stock":
            continue
        ticker = item["ticker"].lower()
        name = item.get("name", "").lower()
        if query not in ticker and query not in name:
            continue
        results.append({
            "ticker": item["ticker"],
            "name": item.get("name") or item["ticker"],
            "sector": item.get("sector") or "Unclassified",
            "industry": item.get("industry"),
        })
    results.sort(key=lambda item: (
        not item["ticker"].lower().startswith(query),
        not item["name"].lower().startswith(query),
        item["name"],
    ))
    return {"results": results[:limit]}


@app.get("/api/company/{ticker}", response_model=CompanyResponse)
def company(ticker: str) -> CompanyResponse:
    try:
        return market_data.company(ticker)
    except MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/company/analyze", response_model=CompanyAnalysisResponse)
def analyze_company(request: CompanyAnalysisRequest) -> CompanyAnalysisResponse:
    symbol = request.ticker.upper().strip()
    item = next(
        (security for security in load_universe()["securities"] if security["ticker"].upper() == symbol),
        None,
    )
    if not item or item["type"] != "stock":
        raise HTTPException(status_code=404, detail="Company is not in the Green Canopy Fortune 1000 universe")
    try:
        company_data = market_data.company(symbol)
        info = market_data.get_info(symbol)
        sustainability = market_data.get_sustainability(symbol)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    assessment = alignment_score(request.profile, item.get("tags", []), sustainability, "stock")
    return CompanyAnalysisResponse(
        **company_data.model_dump(),
        description=info.get("longBusinessSummary"),
        market_cap=info.get("marketCap"),
        green_canopy_score=assessment["alignment_score"],
        green_canopy_confidence=assessment["confidence"],
        matched_priorities=assessment["matched_priorities"],
        assessment_limitations=assessment["limitations"],
    )


@app.post("/api/portfolio/quotes", response_model=QuoteResponse)
def portfolio_quotes(request: QuoteRequest) -> QuoteResponse:
    quotes: list[QuoteItem] = []
    for raw_symbol in dict.fromkeys(request.tickers):
        symbol = raw_symbol.upper().strip()
        if not symbol or len(symbol) > 10:
            continue
        try:
            info = market_data.get_info(symbol)
        except MarketDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            try:
                price = float(market_data.get_history(symbol).iloc[-1])
            except MarketDataError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        quotes.append(QuoteItem(
            ticker=symbol,
            current_price=float(price),
            retrieved_at=market_data._timestamp(),
        ))
    if not quotes:
        raise HTTPException(status_code=400, detail="No valid tickers supplied")
    return QuoteResponse(quotes=quotes)


@app.post("/api/profile", response_model=InvestorProfile)
def profile(request: ProfileRequest) -> InvestorProfile:
    return build_profile(request.answers)


@app.post("/api/portfolio/generate", response_model=PortfolioResponse)
def portfolio(request: PortfolioRequest) -> PortfolioResponse:
    try:
        return generate_portfolio(request, market_data)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/portfolio/analyze", response_model=PortfolioAnalysisResponse)
def portfolio_analysis(request: PortfolioAnalysisRequest) -> PortfolioAnalysisResponse:
    try:
        return analyze_portfolio(request, market_data)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
