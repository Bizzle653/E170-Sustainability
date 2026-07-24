# Green Canopy

Green Canopy is a local educational sustainable-investing portfolio builder. A questionnaire becomes a deterministic investor profile, the FastAPI backend retrieves market and third-party ESG-risk data through `yfinance`, and a constrained SciPy optimizer produces a simulated diversified portfolio with transparent limitations.

It does not connect to a brokerage, execute trades, predict returns, or provide financial advice.

## Investment universe

The bundled universe contains:

- 955 publicly traded companies with usable tickers from a public 2024 Fortune 1000 dataset
- The 100 largest U.S.-listed ETFs by assets recorded from ETF Database on July 23, 2026

The other Fortune 1000 constituents are private or do not have a usable public ticker, so they cannot be queried through `yfinance`. `backend/data/import_fortune_universe.py` can refresh the company entries from a CSV containing `Rank`, `Company`, `Ticker`, `Sector`, `Industry`, and `CompanyType`.

Green Canopy does not fetch all 1,055 securities for every portfolio. It screens the local metadata first, then retrieves a bounded candidate set for reliability and provider-rate-limit safety.

## Project structure

```text
app/
  page.tsx                 Questionnaire and marketing site
  results/page.tsx         Separate portfolio results page
backend/
  main.py                  FastAPI endpoints
  models.py                Pydantic request and response contracts
  services/
    investor_profile.py    Deterministic questionnaire scoring
    market_data.py         yfinance retrieval, metrics, and TTL caches
    sustainability.py      Transparent alignment calculation
    portfolio_optimizer.py SciPy optimization and exact rounding
    portfolio.py           Candidate screening and response assembly
  data/
    investment_universe.json
    import_fortune_universe.py
  tests/                   Offline mocked test suite
  requirements.txt
```

## Local installation (Windows PowerShell)

Prerequisites: Node.js 20+ and Python 3.11+.

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Create `.env.local` at the repository root if the API will run somewhere other than the default:

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Run locally

Open two PowerShell terminals from the repository root.

Backend:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --port 8000
```

Frontend:

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

## Tests and production build

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm run build
```

## API

- `GET /api/health`
- `GET /api/universe`
- `GET /api/company/{ticker}`
- `POST /api/profile`
- `POST /api/portfolio/generate`

## How yfinance is used

The backend retrieves approximately three years of auto-adjusted daily closing prices, recent company/fund information, and Yahoo sustainability fields when available. It calculates annualized historical return, annualized volatility, maximum drawdown, and correlations locally.

In-memory cache lifetimes are 15 minutes for company/quote information, 12 hours for price history, and 24 hours for sustainability responses.

## Sustainability-data limitations

Yahoo sustainability fields are third-party ESG-risk information, not proof that a company or fund creates positive impact. Raw provider fields stay separate from Green Canopy’s calculated user-alignment score. Lower-is-better Yahoo risk-style fields are transformed only after their direction is explicitly identified in code.

Missing sustainability values remain unavailable; they are never replaced with zero or fabricated scores. Stock candidates without required Yahoo sustainability data are normally excluded. ETFs may remain for diversification using clearly labeled Green Canopy classification metadata, but their confidence is reduced and the limitation appears in the result.

Category tags in `investment_universe.json` are Green Canopy classification metadata, not third-party ESG facts. Historical performance is descriptive and does not guarantee future results.
