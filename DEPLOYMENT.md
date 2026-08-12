# Green Canopy Deployment Guide

Green Canopy can run as a single Vercel project or as separate frontend and backend services. The Vercel deployment is the simplest option because the Next.js frontend and FastAPI backend share one origin.

## Option A: Vercel

### Prerequisites

- A GitHub repository containing this project
- A Vercel account connected to GitHub
- A DeepSeek API key
- Optional Supabase project credentials for authentication and persistence

### Project structure

Vercel detects the Next.js application at the repository root. It also detects `api/index.py` as the FastAPI entry point. A rewrite sends public `/api/*` requests to that single Python function while preserving the requested FastAPI path.

```text
Browser
  -> Next.js pages on Vercel
  -> /api/* on the same Vercel origin
  -> api/index.py
  -> backend.main:app
  -> DeepSeek, Yahoo Finance, and optional Supabase services
```

Production does not require `NEXT_PUBLIC_API_URL` when the frontend and backend use the same Vercel project.

### Configure the project

1. Import the GitHub repository at [vercel.com](https://vercel.com).
2. Keep the project root directory set to the repository root.
3. Keep framework detection set to Next.js.
4. Add the required environment variables under **Settings -> Environment Variables**.
5. Deploy the `main` branch.

Required server-side variable:

| Variable | Required | Purpose |
|---|---:|---|
| `DEEPSEEK_API_KEY` | Yes | Authorizes server-side chatbot requests to DeepSeek. |

Optional variables:

| Variable | Required | Purpose |
|---|---:|---|
| `NEXT_PUBLIC_SUPABASE_URL` | No | Enables Supabase authentication and persistence. |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | No | Public Supabase browser client key. |
| `GREEN_CANOPY_ALLOWED_ORIGINS` | No | Comma-separated additional frontend origins for split deployments. |
| `GREEN_CANOPY_AGENT_STATE_URL` | No | Overrides the public GitHub state file used by `/api/agent/status`. |
| `NEXT_PUBLIC_API_URL` | No | External backend origin for an intentional split deployment. Omit for same-origin Vercel deployment. |

Never expose `DEEPSEEK_API_KEY` through a variable prefixed with `NEXT_PUBLIC_`.

### Deploy from GitHub

When the Vercel project is connected to the GitHub repository, a push to `main` should create a production deployment automatically:

```powershell
git add -A
git commit -m "Describe the deployment change"
git push origin main
```

Confirm that the new commit appears under the Vercel project's **Deployments** tab. A successful Git push does not by itself prove that Vercel deployed the commit. Commits that only update `classification_agent_state.json` are intentionally skipped to avoid unnecessary production builds; the live status API reads that public state directly from GitHub.

### Deploy with the Vercel CLI

From the repository root:

```powershell
npx vercel@latest link
npx vercel@latest --prod
```

### Production verification

Replace the placeholder domain with the active Vercel domain:

```text
https://your-project.vercel.app/
https://your-project.vercel.app/api/health
https://your-project.vercel.app/chat
```

Expected health response:

```json
{"status":"ok","service":"Green Canopy API"}
```

After the health check passes, send a chatbot message and test one market-data or portfolio endpoint.

## Option B: Docker Compose

Use this option on a VM with Docker and Docker Compose installed.

### Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add the required credentials. For a browser accessing a separately hosted backend, `NEXT_PUBLIC_API_URL` must be a browser-accessible URL. Do not use the Docker service name as a browser URL.

### Start the services

```bash
docker compose up -d --build
```

Default local addresses:

- Frontend: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- Chat page: `http://localhost:3000/chat`

## Option C: Split Vercel and Python Hosting

The frontend can run on Vercel while FastAPI runs on Render, Railway, or another Python host.

Backend configuration example:

```text
Build command: pip install -r backend/requirements.txt
Start command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Set these backend variables:

```text
DEEPSEEK_API_KEY=your-server-side-key
GREEN_CANOPY_ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

Set this frontend build variable to the public backend origin:

```text
NEXT_PUBLIC_API_URL=https://your-python-backend.example.com
```

## Troubleshooting

### The website opens but `/api/health` returns 500

- Confirm the latest Git commit produced a successful Vercel deployment.
- Inspect the latest deployment's build logs and Python function runtime logs.
- Confirm `api/index.py` exists and exports a top-level FastAPI variable named `app`.
- Confirm root `requirements.txt` includes every imported Python dependency.
- Confirm the configured Python version in `.python-version` is supported by Vercel.

### The browser calls localhost in production

- Remove `NEXT_PUBLIC_API_URL` if the frontend and FastAPI backend share one Vercel project.
- Redeploy after changing any `NEXT_PUBLIC_` environment variable because Next.js embeds it at build time.

### The chatbot returns a service configuration error

- Confirm `DEEPSEEK_API_KEY` exists in the Production environment.
- Redeploy after adding or changing the variable.
- Keep the key server-side and never commit it to Git.
