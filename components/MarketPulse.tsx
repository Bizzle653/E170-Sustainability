"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";

type PricePoint = { date: string; close: number };
type WatchlistItem = {
  ticker: string;
  company_name: string;
  sector: string | null;
  current_price: number;
  change_amount: number;
  change_percent: number;
  period: string;
  interval: string;
  points: PricePoint[];
  blurb: string | null;
};
type CompanyStats = {
  annualized_historical_return: number;
  annualized_volatility: number;
  maximum_drawdown: number;
  description: string | null;
};
type SearchResult = { ticker: string; name: string; sector: string; industry?: string };

const RANGES: { key: string; label: string; period: string; interval: string }[] = [
  { key: "1W", label: "1W", period: "5d", interval: "30m" },
  { key: "1M", label: "1M", period: "1mo", interval: "1d" },
  { key: "3M", label: "3M", period: "3mo", interval: "1d" },
  { key: "1Y", label: "1Y", period: "1y", interval: "1d" },
  { key: "5Y", label: "5Y", period: "5y", interval: "1wk" },
];

const GLOSSARY: { term: string; definition: string }[] = [
  { term: "Closing price", definition: "The price at the end of each trading session. This line connects those closes over time." },
  { term: "% change", definition: "How much the price moved from the first point shown to the last, as a share of the starting price." },
  { term: "Volatility", definition: "How much the price swings up and down over a year. Higher means bigger, less predictable moves." },
  { term: "Maximum drawdown", definition: "The biggest drop from a peak to a low point in the period shown — a rough gauge of “how bad could it get.”" },
];

const money = (value: number) => value.toLocaleString("en-US", { style: "currency", currency: "USD" });
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

function buildPath(points: PricePoint[], width: number, height: number, pad = 3): string {
  if (points.length < 2) return "";
  const values = points.map((point) => point.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = (width - pad * 2) / (points.length - 1);
  return values
    .map((value, index) => {
      const x = pad + index * step;
      const y = pad + (height - pad * 2) * (1 - (value - min) / span);
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function BigChart({ points, positive }: { points: PricePoint[]; positive: boolean }) {
  const width = 640;
  const height = 240;
  const path = buildPath(points, width, height, 12);
  const [hover, setHover] = useState<{ x: number; point: PricePoint } | null>(null);
  if (!path) return <p className="errorMessage">No chart data for this range.</p>;

  const values = points.map((point) => point.close);
  const min = Math.min(...values);
  const max = Math.max(...values);

  function handleMove(event: React.MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const index = Math.round(ratio * (points.length - 1));
    const x = 12 + ((width - 24) / (points.length - 1)) * index;
    setHover({ x, point: points[index] });
  }

  return (
    <div className="chartBig">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
      >
        <path d={path} fill="none" stroke={positive ? "var(--forest-2)" : "#a23b2d"} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {hover && <line x1={hover.x} x2={hover.x} y1={12} y2={height - 12} className="chartCrosshair" />}
        {hover && <circle cx={hover.x} cy={12 + (height - 24) * (1 - (hover.point.close - min) / (max - min || 1))} r={4} fill={positive ? "var(--forest-2)" : "#a23b2d"} />}
      </svg>
      <div className="chartAxis">
        <span>{new Date(points[0].date).toLocaleDateString()}</span>
        {hover && <strong>{hover.point.close.toFixed(2)} &middot; {new Date(hover.point.date).toLocaleDateString()}</strong>}
        <span>{new Date(points[points.length - 1].date).toLocaleDateString()}</span>
      </div>
    </div>
  );
}

function useWatchlist() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch(apiUrl("/api/market/watchlist"))
      .then((response) => {
        if (!response.ok) throw new Error("Market data is temporarily unavailable");
        return response.json();
      })
      .then((payload) => {
        if (!cancelled) setItems(payload.items ?? []);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Market data is temporarily unavailable");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { items, loading, error };
}

/** Live-ticker strip that sits inside the hero, next to the garden photo, so the site
 * reads as a finance app on first glance. Tapping a chip opens the full chart directly
 * -- this is the only market-data surface on the page, deliberately not duplicated
 * further down, so a visitor only ever sees one set of graphs. */
export function HeroTicker() {
  const { items, loading, error } = useWatchlist();
  const [selected, setSelected] = useState<WatchlistItem | null>(null);
  const [range, setRange] = useState(RANGES[1]);
  const [detail, setDetail] = useState<WatchlistItem | null>(null);
  const [stats, setStats] = useState<CompanyStats | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [opening, setOpening] = useState<string | null>(null);
  const [searchError, setSearchError] = useState("");

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError("");
    try {
      const response = await fetch(apiUrl(`/api/universe/search?q=${encodeURIComponent(query)}&limit=8`));
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Search failed");
      setResults(payload.results ?? []);
    } catch (reason) {
      setSearchError(reason instanceof Error ? reason.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function openSearchResult(result: SearchResult) {
    setOpening(result.ticker);
    setSearchError("");
    try {
      const response = await fetch(apiUrl(`/api/market/sparkline/${result.ticker}?period=1mo&interval=1d`));
      if (!response.ok) throw new Error(`Chart data is unavailable for ${result.ticker}`);
      const payload: WatchlistItem = await response.json();
      setSelected(payload);
      setDetail(payload);
      setRange(RANGES[1]);
      setStats(null);
      setDetailError("");
      setResults([]);
      setQuery("");
      void loadStats(result.ticker);
    } catch (reason) {
      setSearchError(reason instanceof Error ? reason.message : `Chart data is unavailable for ${result.ticker}`);
    } finally {
      setOpening(null);
    }
  }

  function openTicker(item: WatchlistItem) {
    setSelected(item);
    setDetail(item);
    setRange(RANGES[1]);
    setStats(null);
    setDetailError("");
    void loadStats(item.ticker);
  }

  async function loadStats(ticker: string) {
    try {
      const response = await fetch(apiUrl(`/api/company/${ticker}`));
      if (!response.ok) throw new Error("Company details are unavailable");
      const payload = await response.json();
      setStats(payload);
    } catch {
      setStats(null);
    }
  }

  async function loadRange(item: WatchlistItem, nextRange: typeof RANGES[number]) {
    setRange(nextRange);
    setDetailLoading(true);
    setDetailError("");
    try {
      const response = await fetch(apiUrl(`/api/market/sparkline/${item.ticker}?period=${nextRange.period}&interval=${nextRange.interval}`));
      if (!response.ok) throw new Error("Chart data is unavailable for that range");
      const payload = await response.json();
      setDetail(payload);
    } catch (reason) {
      setDetailError(reason instanceof Error ? reason.message : "Chart data is unavailable for that range");
    } finally {
      setDetailLoading(false);
    }
  }

  if (loading || error || items.length === 0) return null;

  return (
    <>
      <div className="heroTicker">
        <div className="heroTickerTop">
          <span className="heroTickerLabel">Live market data via Yahoo Finance</span>
          <form className="heroSearch" onSubmit={search}>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search Green Canopy companies"
              aria-label="Search Green Canopy companies"
            />
            <button disabled={searching || !query.trim()}>{searching ? "…" : "Search"}</button>
          </form>
        </div>

        {searchError && <p className="errorMessage heroSearchError">{searchError}</p>}
        {results.length > 0 && (
          <div className="searchResults heroSearchResults">
            {results.map((item) => (
              <button key={item.ticker} onClick={() => openSearchResult(item)} disabled={opening === item.ticker}>
                <span className="tickerBadge">{item.ticker}</span>
                <span><strong>{item.name}</strong><small>{item.sector}{item.industry ? ` · ${item.industry}` : ""}</small></span>
                <b>{opening === item.ticker ? "…" : "View"}</b>
              </button>
            ))}
          </div>
        )}

        <div className="heroTickerRow">
          {items.map((item) => {
            const positive = item.change_percent >= 0;
            const path = buildPath(item.points, 44, 20);
            return (
              <button className="heroChip" key={item.ticker} onClick={() => openTicker(item)}>
                <b>{item.ticker}</b>
                {path && (
                  <svg width="44" height="20" viewBox="0 0 44 20" preserveAspectRatio="none" aria-hidden="true">
                    <path d={path} fill="none" stroke={positive ? "var(--forest-2)" : "#a23b2d"} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
                <small className={positive ? "positive" : "negative"}>{positive ? "+" : ""}{pct(item.change_percent)}</small>
              </button>
            );
          })}
        </div>
      </div>

      {selected && detail && (
        <div className="modalBackdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}>
          <section className="companyReview marketReview" role="dialog" aria-modal="true" aria-labelledby="market-review-title">
            <button className="reviewClose" onClick={() => setSelected(null)} aria-label="Close chart">&times;</button>
            <header>
              <div>
                <span className="tickerBadge">{selected.ticker}</span>
                <span className="eyebrow">{selected.sector ?? "Market data"}</span>
                <h2 id="market-review-title">{selected.company_name}</h2>
              </div>
              <div className="reviewPrice">
                <small>Latest close</small>
                <strong>{money(detail.current_price)}</strong>
                <span className={detail.change_percent >= 0 ? "positive" : "negative"}>{detail.change_percent >= 0 ? "+" : ""}{pct(detail.change_percent)} over this range</span>
              </div>
            </header>

            <div className="rangeToggle">
              {RANGES.map((option) => (
                <button
                  key={option.key}
                  className={option.key === range.key ? "active" : ""}
                  onClick={() => loadRange(selected, option)}
                  disabled={detailLoading}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {detailError && <p className="errorMessage">{detailError}</p>}
            <BigChart points={detail.points} positive={detail.change_percent >= 0} />

            {stats && (
              <div className="reviewMetrics">
                <Metric label="Historical annual return" value={pct(stats.annualized_historical_return)} note="3-year period · not a forecast" />
                <Metric label="Historical volatility" value={pct(stats.annualized_volatility)} note="Annualized" />
                <Metric label="Maximum drawdown" value={pct(stats.maximum_drawdown)} note="Observed period" />
              </div>
            )}

            <div className="reviewBody">
              <div>
                <h3>What am I looking at?</h3>
                <p>{detail.blurb}</p>
                <div className="chartGlossary">
                  {GLOSSARY.map((entry) => (
                    <p key={entry.term}><b>{entry.term}:</b> {entry.definition}</p>
                  ))}
                </div>
              </div>
              <div>
                <h3>About {selected.company_name}</h3>
                <p>{stats?.description || "A detailed company description was not available from the provider."}</p>
              </div>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
