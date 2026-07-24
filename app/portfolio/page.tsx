"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { AccountGate } from "@/components/AccountGate";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthProvider";
import { getSupabaseBrowserClient } from "@/lib/supabase";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
const PORTFOLIO_KEY = "greenCanopyPortfolio";
const QUOTE_KEY = "greenCanopyQuotes";
const QUOTE_TTL = 15 * 60 * 1000;

type Profile = {
  profile_name: string;
  profile_description: string;
  risk_score: number;
  sustainability_priority_weights: Record<string, number>;
  exclusions: string[];
  time_horizon: string;
  investment_objective: string;
  sustainability_tradeoff: string;
  company_preference: string;
  max_concentration: number;
};
type Allocation = {
  ticker: string; name: string; asset_type: string; sector: string; weight: number;
  dollar_amount: number; purchase_price?: number; shares?: number; alignment_score: number;
  confidence: string; matched_priorities: string[]; why_selected: string; sustainability_status: string;
};
type Portfolio = {
  investor_profile: Profile; total_investment_amount: number; allocations: Allocation[];
  sustainability_alignment_score: number; annualized_historical_return: number;
  annualized_volatility: number; maximum_drawdown: number; number_of_holdings: number;
  sector_distribution: Record<string, number>; diversification_score: number;
  data_retrieved_at: string; sources: string[]; warnings: string[]; limitations: string[];
  tracking_started_at?: string; user_modified?: boolean;
};
type SearchResult = { ticker: string; name: string; sector: string; industry?: string };
type Analysis = {
  ticker: string; company_name: string; sector?: string; industry?: string; current_price: number;
  price_retrieved_at: string; annualized_historical_return: number; annualized_volatility: number;
  maximum_drawdown: number; yahoo_sustainability: {status: string; raw_fields: Record<string, unknown>; retrieved_at: string};
  description?: string; market_cap?: number; green_canopy_score: number; green_canopy_confidence: string;
  matched_priorities: string[]; assessment_limitations: string[];
};
type QuoteCache = { updatedAt: number; prices: Record<string, number> };

const money = (value: number) => value.toLocaleString("en-US", {style: "currency", currency: "USD"});
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function PortfolioDashboard() {
  return <AccountGate><AppShell><PortfolioContent /></AppShell></AccountGate>;
}

function PortfolioContent() {
  const {user} = useAuth();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [addAmount, setAddAmount] = useState(500);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const raw = localStorage.getItem(PORTFOLIO_KEY) ?? sessionStorage.getItem(PORTFOLIO_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as Portfolio;
        setPortfolio(saved);
        if (!localStorage.getItem(PORTFOLIO_KEY)) localStorage.setItem(PORTFOLIO_KEY, raw);
      }
      const quoteRaw = localStorage.getItem(QUOTE_KEY);
      if (quoteRaw) {
        const cache = JSON.parse(quoteRaw) as QuoteCache;
        setPrices(cache.prices);
        setUpdatedAt(cache.updatedAt);
      }
      const supabase = getSupabaseBrowserClient();
      if (supabase && user) {
        void supabase.from("portfolios").select("data").eq("user_id", user.id).maybeSingle().then(({data}) => {
          if (data?.data) {
            const saved = data.data as Portfolio;
            setPortfolio(saved);
            localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(saved));
          } else if (raw) {
            void supabase.from("portfolios").upsert({user_id: user.id, data: JSON.parse(raw), updated_at: new Date().toISOString()});
          }
        });
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [user]);

  const holdings = useMemo(() => portfolio?.allocations.map((item) => {
    const price = prices[item.ticker] ?? item.purchase_price ?? (item.shares ? item.dollar_amount / item.shares : 0);
    const purchasePrice = item.purchase_price ?? price;
    const shares = item.shares ?? (purchasePrice ? item.dollar_amount / purchasePrice : 0);
    const currentValue = shares * price;
    return {...item, price, purchasePrice, shares, currentValue, gain: currentValue - item.dollar_amount};
  }) ?? [], [portfolio, prices]);
  const currentValue = holdings.reduce((sum, item) => sum + item.currentValue, 0);
  const totalGain = portfolio ? currentValue - portfolio.total_investment_amount : 0;
  const totalReturn = portfolio?.total_investment_amount ? totalGain / portfolio.total_investment_amount : 0;

  function savePortfolio(next: Portfolio) {
    localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(next));
    setPortfolio(next);
    const supabase = getSupabaseBrowserClient();
    if (supabase && user) {
      void supabase.from("portfolios").upsert({user_id: user.id, data: next, updated_at: new Date().toISOString()});
    }
  }

  async function refreshQuotes(force = false) {
    if (!portfolio || refreshing) return;
    if (!force && updatedAt && Date.now() - updatedAt < QUOTE_TTL) return;
    setRefreshing(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/portfolio/quotes`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({tickers: portfolio.allocations.map((item) => item.ticker)}),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Prices are temporarily unavailable");
      const nextPrices = Object.fromEntries(payload.quotes.map((item: {ticker: string; current_price: number}) => [item.ticker, item.current_price]));
      const now = Date.now();
      setPrices(nextPrices);
      setUpdatedAt(now);
      localStorage.setItem(QUOTE_KEY, JSON.stringify({prices: nextPrices, updatedAt: now}));

      if (portfolio.allocations.some((item) => !item.purchase_price || !item.shares)) {
        savePortfolio({
          ...portfolio,
          tracking_started_at: portfolio.tracking_started_at ?? new Date(now).toISOString(),
          allocations: portfolio.allocations.map((item) => {
            const basis = item.purchase_price ?? nextPrices[item.ticker];
            return {...item, purchase_price: basis, shares: item.shares ?? item.dollar_amount / basis};
          }),
        });
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Prices are temporarily unavailable");
    } finally {
      setRefreshing(false);
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/universe/search?q=${encodeURIComponent(query)}&limit=10`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Search failed");
      setResults(payload.results);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function reviewCompany(company: SearchResult) {
    if (!portfolio) return;
    setReviewing(true);
    setAnalysis(null);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/company/analyze`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ticker: company.ticker, profile: portfolio.investor_profile}),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Company analysis is unavailable");
      setAnalysis(payload);
      setAddAmount(Math.max(100, Math.round(portfolio.total_investment_amount * 0.05 / 50) * 50));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Company analysis is unavailable");
    } finally {
      setReviewing(false);
    }
  }

  function addCompany() {
    if (!portfolio || !analysis) return;
    if (portfolio.allocations.some((item) => item.ticker === analysis.ticker)) {
      setError(`${analysis.ticker} is already in this portfolio.`);
      setAnalysis(null);
      return;
    }
    const amount = Math.min(Math.max(addAmount, 100), portfolio.total_investment_amount * 0.2);
    const remaining = portfolio.total_investment_amount - amount;
    const scaled = portfolio.allocations.map((item) => {
      const dollars = item.dollar_amount / portfolio.total_investment_amount * remaining;
      const basis = item.purchase_price ?? prices[item.ticker] ?? 0;
      return {
        ...item,
        dollar_amount: Math.round(dollars * 100) / 100,
        weight: Math.round(dollars / portfolio.total_investment_amount * 10000) / 100,
        shares: basis ? dollars / basis : item.shares,
      };
    });
    const added: Allocation = {
      ticker: analysis.ticker,
      name: analysis.company_name,
      asset_type: "stock",
      sector: analysis.sector ?? "Unclassified",
      weight: Math.round(amount / portfolio.total_investment_amount * 10000) / 100,
      dollar_amount: amount,
      purchase_price: analysis.current_price,
      shares: amount / analysis.current_price,
      alignment_score: analysis.green_canopy_score,
      confidence: analysis.green_canopy_confidence,
      matched_priorities: analysis.matched_priorities,
      why_selected: "Added by you after reviewing its financial and sustainability data.",
      sustainability_status: analysis.yahoo_sustainability.status,
    };
    const allocations = [...scaled, added];
    const sectorDistribution = allocations.reduce<Record<string, number>>((acc, item) => {
      acc[item.sector] = (acc[item.sector] ?? 0) + item.weight;
      return acc;
    }, {});
    const alignmentScore = allocations.reduce((sum, item) => sum + item.alignment_score * item.weight / 100, 0);
    savePortfolio({
      ...portfolio,
      allocations,
      number_of_holdings: allocations.length,
      sustainability_alignment_score: Math.round(alignmentScore * 10) / 10,
      sector_distribution: sectorDistribution,
      user_modified: true,
    });
    const now = Date.now();
    const nextPrices = {...prices, [analysis.ticker]: analysis.current_price};
    setPrices(nextPrices);
    setUpdatedAt(now);
    localStorage.setItem(QUOTE_KEY, JSON.stringify({prices: nextPrices, updatedAt: now}));
    setAnalysis(null);
    setResults([]);
    setQuery("");
  }

  if (!portfolio) return <main className="emptyResults"><div className="brand"><span className="brandMark">⌁</span><span>Green Canopy</span></div><h1>Your canopy is ready to grow.</h1><p>Generate a portfolio first, then it will appear here on this device.</p><Link className="button" href="/">Generate a portfolio</Link></main>;

  return <main className="dashboardPage shellDashboard">
    <section className="dashboardHero">
      <div><span className="eyebrow lightEyebrow">Your outstanding portfolio</span><h1>{portfolio.investor_profile.profile_name}</h1><p>Saved on this device · Educational simulation · No trades are executed</p></div>
      <button className="refreshButton" onClick={() => refreshQuotes(true)} disabled={refreshing}>{refreshing ? "Refreshing…" : "Refresh market prices"}</button>
    </section>

    <section className="performanceGrid">
      <Metric label="Initial investment" value={money(portfolio.total_investment_amount)} note="Original simulated capital" />
      <Metric label="Current value" value={money(currentValue || portfolio.total_investment_amount)} note={updatedAt ? `Prices checked ${new Date(updatedAt).toLocaleString()}` : "Refresh to begin tracking"} />
      <Metric label="Total return" value={updatedAt ? money(totalGain) : "—"} note={updatedAt ? pct(totalReturn) : "Waiting for current prices"} tone={totalGain >= 0 ? "positive" : "negative"} />
      <Metric label="Alignment" value={`${portfolio.sustainability_alignment_score}/100`} note="Green Canopy score" />
    </section>

    <section className="dashboardGrid">
      <div className="dashboardPanel holdingsPanel">
        <div className="panelHeader"><div><span className="eyebrow">Portfolio</span><h2>Your holdings</h2></div><strong>{holdings.length} companies & funds</strong></div>
        <div className="dashboardTable">
          <div className="tableHeader"><span>Holding</span><span>Invested</span><span>Current</span><span>Return</span><span>Alignment</span></div>
          {holdings.map((item) => <div className="dashboardRow" key={item.ticker}>
            <div><span className="tickerBadge">{item.ticker}</span><p><strong>{item.name}</strong><small>{item.shares.toFixed(4)} shares · {item.sector}</small></p></div>
            <span>{money(item.dollar_amount)}</span>
            <span>{updatedAt ? money(item.currentValue) : "—"}<small>{updatedAt ? `${money(item.price)} / share` : "Refresh prices"}</small></span>
            <span className={item.gain >= 0 ? "positive" : "negative"}>{updatedAt ? money(item.gain) : "—"}</span>
            <span>{item.alignment_score}/100</span>
          </div>)}
        </div>
      </div>

      <aside className="dashboardPanel searchPanel">
        <span className="eyebrow">Explore the universe</span><h2>Add a company</h2><p>Search the Fortune 1000 universe. You must review the company before adding it.</p>
        <form className="companySearch" onSubmit={search}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ticker or company name" aria-label="Search companies" /><button disabled={searching}>{searching ? "…" : "Search"}</button></form>
        {error && <p className="errorMessage">{error}</p>}
        <div className="searchResults">{results.map((item) => <button key={item.ticker} onClick={() => reviewCompany(item)} disabled={reviewing}><span className="tickerBadge">{item.ticker}</span><span><strong>{item.name}</strong><small>{item.sector}{item.industry ? ` · ${item.industry}` : ""}</small></span><b>{reviewing ? "…" : "Review"}</b></button>)}</div>
        <small className="dataNote">Company search uses the local Green Canopy universe and does not call Yahoo. Detailed data is requested only when you open a review.</small>
      </aside>
    </section>

    {analysis && <div className="modalBackdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setAnalysis(null); }}>
      <section className="companyReview" role="dialog" aria-modal="true" aria-labelledby="company-review-title">
        <button className="reviewClose" onClick={() => setAnalysis(null)} aria-label="Close company review">×</button>
        <header><div><span className="tickerBadge">{analysis.ticker}</span><span className="eyebrow">Pre-add review</span><h2 id="company-review-title">{analysis.company_name}</h2><p>{analysis.sector} · {analysis.industry ?? "Industry unavailable"}</p></div><div className="reviewPrice"><small>Current tracker</small><strong>{money(analysis.current_price)}</strong><span>Checked {new Date(analysis.price_retrieved_at).toLocaleString()}</span></div></header>
        <div className="reviewMetrics">
          <Metric label="Historical annual return" value={pct(analysis.annualized_historical_return)} note="3-year period · not a forecast" />
          <Metric label="Historical volatility" value={pct(analysis.annualized_volatility)} note="Annualized" />
          <Metric label="Maximum drawdown" value={pct(analysis.maximum_drawdown)} note="Observed period" />
          <Metric label="Green Canopy score" value={`${analysis.green_canopy_score}/100`} note={`${analysis.green_canopy_confidence} confidence`} />
        </div>
        <div className="reviewBody">
          <div><h3>About the company</h3><p>{analysis.description || "A detailed company description was not available from the provider."}</p></div>
          <div><h3>Yahoo ESG risk fields</h3>{analysis.yahoo_sustainability.status === "available" ? <div className="esgGrid">{["totalEsg", "environmentScore", "socialScore", "governanceScore", "highestControversy"].map((key) => <span key={key}><small>{key.replace(/([A-Z])/g, " $1")}</small><strong>{String(analysis.yahoo_sustainability.raw_fields[key] ?? "—")}</strong></span>)}</div> : <p>No Yahoo sustainability fields are currently available. Green Canopy does not invent missing ESG data.</p>}<small>Yahoo’s ESG fields are risk indicators; lower values are generally better. The Green Canopy score is a separate educational alignment measure.</small></div>
        </div>
        <footer className="reviewFooter"><label>Reallocate to this company <span>{money(addAmount)}</span><input type="range" min="100" max={Math.max(100, portfolio.total_investment_amount * 0.2)} step="50" value={addAmount} onChange={(event) => setAddAmount(Number(event.target.value))} /><small>This proportionally reduces the other simulated positions so the original investment stays unchanged.</small></label><button className="button" onClick={addCompany}>Add to my portfolio</button></footer>
      </section>
    </div>}
  </main>;
}

function Metric({label, value, note, tone = ""}:{label: string; value: string; note: string; tone?: string}) {
  return <div className={tone}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}
