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

## Deploy on Vercel

The repository includes `api/backend.py`, which exposes the existing FastAPI application as a Vercel Python Function. Vercel rewrites public `/api/...` requests to that function while preserving the API path. In production the frontend uses same-origin requests, so it does not need `NEXT_PUBLIC_API_URL`.

Deploy the repository as one Vercel project:

```powershell
vercel --prod
```

Do not set `NEXT_PUBLIC_API_URL` to `localhost` in Vercel. If that variable already exists in the Vercel project, remove it and redeploy. It is only needed when the frontend and backend intentionally use different hosts.

Additional direct frontend origins can be allowed with a comma-separated server-side environment variable:

```text
GREEN_CANOPY_ALLOWED_ORIGINS=https://example.com,https://preview.example.com
```

## Tests and production build

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm run build
```

## API

- `GET /api/health`
- `GET /api/universe`
- `GET /api/universe/search?q=microsoft`
- `GET /api/company/{ticker}`
- `POST /api/company/analyze`
- `POST /api/profile`
- `POST /api/portfolio/generate`
- `POST /api/portfolio/quotes`

## Portfolio dashboard

Generated portfolios can be opened at `/portfolio`. When Supabase is connected,
the dashboard associates portfolios, profiles, and settings with the signed-in
user and synchronizes them across sessions. The dashboard tracks simulated
returns, searches the local company universe without a market-data request, and
requires a full company review before a user-directed reallocation. This MVP
does not execute trades.

## Accounts and authentication

Green Canopy uses Supabase Auth for managed email/password authentication and
Supabase Postgres with row-level security for user-owned records. Passwords are
not handled or stored by Green Canopy.

1. Create a Supabase project.
2. Run `supabase/schema.sql` in the Supabase SQL editor.
3. Copy `.env.example` to `.env.local` and set:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
4. Add the production `/portfolio` and `/settings` URLs to the Supabase Auth
   redirect allow list.

The login, profile, settings, password-reset, email-change, and logout interfaces
remain visibly unavailable until those environment values are connected.

## How yfinance is used

The backend retrieves approximately three years of auto-adjusted daily closing prices, recent company/fund information, and Yahoo sustainability fields when available. It calculates annualized historical return, annualized volatility, maximum drawdown, and correlations locally.

In-memory cache lifetimes are 15 minutes for company/quote information, 12 hours for price history, and 24 hours for sustainability responses.

## Sustainability-data limitations

Yahoo sustainability fields are third-party ESG-risk information, not proof that a company or fund creates positive impact. Raw provider fields stay separate from Green Canopy’s calculated user-alignment score. Lower-is-better Yahoo risk-style fields are transformed only after their direction is explicitly identified in code.

Missing sustainability values remain unavailable; they are never replaced with zero or fabricated scores. Stock candidates without required Yahoo sustainability data are normally excluded. ETFs may remain for diversification using clearly labeled Green Canopy classification metadata, but their confidence is reduced and the limitation appears in the result.

Category tags in `investment_universe.json` are Green Canopy classification metadata, not third-party ESG facts. Historical performance is descriptive and does not guarantee future results.

## Appropriate use of generative AI

The current investment selection and allocation are deterministic; no language model chooses securities or invents sustainability evidence. A future generative-AI layer could explain the completed structured result in more accessible language, answer questions about why holdings were selected, or summarize trade-offs. It should receive only the calculated profile, allocations, metrics, and limitations, and it must never replace the optimizer, create missing ESG values, or present generated text as financial advice.
