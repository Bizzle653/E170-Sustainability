# Green Canopy

Green Canopy is an educational sustainable-investing portfolio builder. A questionnaire becomes a deterministic investor profile, the FastAPI backend retrieves market data through `yfinance`, and a constrained SciPy optimizer produces a simulated diversified portfolio with transparent limitations. An autonomous Sustainability Intelligence Agent researches and continuously updates Green Canopy's internal classification metadata without controlling portfolio weights or executing trades.

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
  classification_agent.py  Autonomous classification-agent CLI
  main.py                  FastAPI endpoints
  models.py                Pydantic request and response contracts
  services/
    investor_profile.py    Deterministic questionnaire scoring
    market_data.py         yfinance retrieval, metrics, and TTL caches
    classification_intelligence.py Evidence collection, AI classification, versioning, and announcements
    sustainability.py      Transparent alignment calculation
    portfolio_optimizer.py SciPy optimization and exact rounding
    portfolio.py           Candidate screening and response assembly
  data/
    investment_universe.json
    classification_updates.json
    classification_agent_state.json
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

The repository includes `api/index.py`, which exposes the existing FastAPI application through one Vercel Python Function. Vercel rewrites public `/api/...` requests to that function while preserving the requested FastAPI path. In production the frontend uses same-origin requests, so it does not need `NEXT_PUBLIC_API_URL`.

Before deploying, add this server-side environment variable in the Vercel project settings for Production, Preview, and Development as needed:

```text
DEEPSEEK_API_KEY=your-real-deepseek-api-key
```

Do not prefix this variable with `NEXT_PUBLIC_`; the key must remain available only to the Python backend. The public browser calls `/api/chat` on the deployed site, and that server-side function calls DeepSeek using the secret.

Deploy the repository as one Vercel project:

```powershell
vercel --prod
```

Do not set `NEXT_PUBLIC_API_URL` to `localhost` in Vercel. If that variable already exists in the Vercel project, remove it and redeploy. It is only needed when the frontend and backend intentionally use different hosts. As a safety net, production builds ignore a localhost value and fall back to the same-origin API.

After deployment, verify both endpoints from the public site:

```text
https://your-project.vercel.app/api/health
https://your-project.vercel.app/chat
```

The health endpoint should return a JSON response with `"status": "ok"`. Then send a message from `/chat` to verify the DeepSeek key is configured correctly.

Additional direct frontend origins can be allowed with a comma-separated server-side environment variable:

```text
GREEN_CANOPY_ALLOWED_ORIGINS=https://example.com,https://preview.example.com
```

For autonomous scheduled classification, add `DEEPSEEK_API_KEY` as a GitHub Actions repository secret. The workflow needs repository `contents: write` permission because accepted classifications and their public announcements are committed back to `main`. Connect the Vercel project to this GitHub repository with `main` as its production branch so those commits are deployed automatically without a separate deployment token.

## Tests and production build

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm run build
npm run test:frontend
```

## API

- `GET /api/health`
- `GET /api/universe`
- `GET /api/universe/search?q=microsoft`
- `GET /api/classifications/updates`
- `GET /api/classifications/{ticker}`
- `GET /api/agent/status`
- `GET /api/company/{ticker}`
- `POST /api/company/analyze`
- `POST /api/profile`
- `POST /api/portfolio/generate`
- `POST /api/portfolio/quotes`
- `POST /api/portfolio/analyze`
- `POST /api/chat`

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

The DeepSeek chatbot can also call the internal `get_yfinance_data` function tool. It supports:

- current quote fields such as price, previous close, daily range, volume, and market capitalization
- company or fund profiles
- bounded, auto-adjusted OHLCV price history with selectable periods and intervals
- ETF and mutual-fund top holdings when Yahoo Finance provides them

The tool validates ticker syntax, restricts history parameters, caps returned rows, and includes the data source and UTC retrieval time in every response. It is an internal model tool exposed through `POST /api/chat`, not a separate public HTTP endpoint.

## Autonomous Sustainability Intelligence Agent

The repository includes an autonomous classification agent that maintains Green Canopy's sustainability tags and exclusion flags. It is separate from the chatbot and never chooses securities, changes portfolio weights, connects to a brokerage, or executes trades.

For each selected company or ETF, the agent:

1. retrieves the current company or fund profile through `yfinance`;
2. retrieves Yahoo sustainability fields when available and ETF top holdings when Yahoo provides them;
3. follows the official website from the market profile and looks for bounded sustainability, ESG, climate, impact, or annual-report evidence;
4. extracts text from supported official HTML pages and PDFs;
5. asks DeepSeek to assess every Green Canopy category using only the numbered evidence bundle;
6. requires short exact quotations that the program can find in the cited source text;
7. sends proposed additions and removals through a separate conservative model-verification pass;
8. rejects incomplete responses, unsupported quotes, low-confidence changes, single-source changes when multiple sources are available, and removals based only on missing evidence;
9. directly applies accepted additions or removals to `investment_universe.json`;
10. versions the universe and publishes a detailed record to `classification_updates.json`.

There is no manual approval step. The automatic-addition threshold defaults to 80%, while removals require at least 90%. Evidence that does not clear every deterministic and model-verification gate leaves the current classification unchanged. Every applied change records the old and new labels, rationale, confidence, exact quotes, source-content hashes, retrieval time, model, policy and prompt versions, possible claim conflicts, and portfolio-impact limitation. Public announcements are paginated at `/classification-updates` and through the classification API.

Legacy static labels are explicitly treated as unreviewed until the Agent verifies their current supporting evidence. Unreviewed or stale labels receive reduced scoring weight and can never produce a high-confidence alignment result. Coverage, the latest run, and the bounded retry queue are public at `/agent-status`.

Run a dry research pass locally:

```powershell
.\.venv\Scripts\python.exe -m backend.classification_agent --tickers MSFT,ICLN
```

Apply changes and publish announcements into the local data files:

```powershell
.\.venv\Scripts\python.exe -m backend.classification_agent --tickers MSFT,ICLN --apply
```

`.github/workflows/sustainability-intelligence-agent.yml` runs the same agent daily in bounded batches of 20, prioritizing retries and unreviewed securities whose current metadata already affects scores. Successful results are published even when another security in the batch fails; failures enter an exponential-backoff retry queue. The connected Vercel Git integration automatically deploys meaningful classification changes pushed to `main`. Operational-state-only commits are intentionally skipped by Vercel and are read by the status API directly from the public repository. The workflow can also be run manually with specific tickers from the GitHub Actions page.

The official-site collector rejects non-public network destinations, restricts followed research links to the issuer's host or subdomains, streams bounded response sizes, follows a bounded number of redirects and documents, and treats retrieval failures as unavailable evidence rather than inventing a result. A label remains Green Canopy classification metadata—not a third-party ESG rating—even after the AI agent updates it.

## Sustainability-data limitations

Yahoo discontinued its free ESG/sustainability API endpoint (it now returns HTTP 404 for every ticker), so those third-party ESG fields are currently unavailable across the board. The scoring code still supports them if Yahoo restores the endpoint. Alignment scores are otherwise driven by Green Canopy's own versioned classification tags, including evidence-backed updates made by the Sustainability Intelligence Agent. Missing sustainability values are never replaced with zero or fabricated scores.

Stock candidates are no longer excluded for lacking Yahoo sustainability data — since that data is universally unavailable right now, requiring it would have silently removed all 955 individual stocks from consideration, leaving only ETFs.

Category tags in `investment_universe.json` are Green Canopy classification metadata, not third-party ESG facts. Agent confidence measures whether the supplied evidence supports a metadata change; it is not an ESG score or an assurance that a company is sustainable. Historical performance is descriptive and does not guarantee future results.

## Appropriate use of generative AI

Investment selection and allocation remain deterministic; no language model chooses securities or sets portfolio weights. Generative AI is used for two bounded purposes: the explanatory chatbot and the autonomous classification agent's interpretation of retrieved evidence. The classification agent can change Green Canopy metadata, but it cannot invent sources: production changes require valid evidence IDs collected by the program and a configured confidence threshold. Every change is versioned and announced publicly.

AI-generated classification can still be wrong or incomplete. Official company publications are self-reported, top-holdings coverage may be partial, reports may be stale, and a model can misinterpret legitimate evidence. The public change log makes those limitations inspectable and the Git history makes every classification change reversible. AI output must never be presented as financial advice, a third-party ESG rating, or a guarantee of future performance.

## Security and automated quality checks

Costly public endpoints use per-client request limits, and a single chatbot request has hard caps on model turns, tool calls, and tool-output size. The application limiter is a server-instance safety net; production usage and DeepSeek billing limits should still be monitored at the providers because serverless instances do not share memory.

`.github/workflows/ci.yml` runs the Python tests, ESLint, frontend interaction tests, the production build, and a production-dependency security audit on every pull request and push to `main`.
