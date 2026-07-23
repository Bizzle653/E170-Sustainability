# Green Canopy

Personalized sustainable investing prototype — a Next.js site you can deploy on Vercel.

## Prerequisites

- Node.js 20 or newer (22+ recommended)

## Local development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy on Vercel

1. Push this repository to GitHub.
2. Import the repo in [Vercel](https://vercel.com/new).
3. Leave **Root Directory** blank (the app lives at the repo root).
4. Framework Preset: **Next.js** (auto-detected).
5. Deploy.

Production build:

```bash
npm run build
npm start
```

## Project shape

- `app/` — pages and styles (`page.tsx` is the marketing site + portfolio builder)
- `public/` — static assets (`favicon.svg`, `og.png`, hero image)

Educational prototype only — illustrative portfolios, not investment advice.
