"use client";

import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";
import { AlignmentDetail, WhyThis } from "@/components/WhyThis";
import { downloadCsv } from "@/lib/csv";

type Allocation = {
  ticker: string; name: string; asset_type: string; sector: string; weight: number;
  dollar_amount: number; purchase_price: number; shares: number; alignment_score: number; confidence: string;
  matched_priorities: string[]; why_selected: string; sustainability_status: string; detail: AlignmentDetail;
  business_summary: string | null;
};
type Benchmark = {ticker: string; name: string; annualized_historical_return: number; annualized_volatility: number; maximum_drawdown: number};
type Portfolio = {
  investor_profile: {profile_name: string; profile_description: string; risk_score: number; sustainability_priority_weights: Record<string, number>};
  total_investment_amount: number; allocations: Allocation[]; sustainability_alignment_score: number; portfolio_narrative: string;
  annualized_historical_return: number; annualized_volatility: number; maximum_drawdown: number; benchmark: Benchmark | null;
  number_of_holdings: number; sector_distribution: Record<string, number>; diversification_score: number;
  data_retrieved_at: string; sources: string[]; warnings: string[]; limitations: string[];
};

function downloadPortfolioCsv(portfolio: Portfolio) {
  const headers = ["Ticker", "Name", "Type", "Sector", "Weight %", "Dollar Amount", "Shares", "Purchase Price", "Alignment Score", "Confidence", "Matched Priorities", "Why Selected"];
  const rows = portfolio.allocations.map((a) => [
    a.ticker, a.name, a.asset_type, a.sector, a.weight, a.dollar_amount, a.shares, a.purchase_price, a.alignment_score, a.confidence, a.matched_priorities.join("; "), a.why_selected,
  ]);
  downloadCsv(`green-canopy-portfolio-${new Date().toISOString().slice(0, 10)}.csv`, headers, rows);
}

const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
const money = (value: number) => value.toLocaleString("en-US", {style: "currency", currency: "USD"});
const GLOSSARY: [string, string][] = [
  ["Alignment score", "How well this portfolio matches the priorities you chose, on a 0-100 scale. It is not a percentage of anything."],
  ["Confidence", "How strongly a holding matches your priorities — high means 2 or more matches, medium means 1, low means none."],
  ["Diversification score", "Higher means your money is spread across more industries instead of concentrated in one."],
  ["Volatility", "How much a holding's value has swung year to year historically. Higher is bumpier, not automatically worse."],
  ["Maximum drawdown", "The worst peak-to-low drop over the historical period shown — a sense of the roughest ride you'd have lived through."],
];

export default function ResultsPage() {
  const stored = useSyncExternalStore(
    () => () => undefined,
    () => localStorage.getItem("greenCanopyPortfolio") ?? sessionStorage.getItem("greenCanopyPortfolio"),
    () => null,
  );
  const portfolio = useMemo<Portfolio | null>(() => stored ? JSON.parse(stored) : null, [stored]);

  if (!portfolio) return <main className="emptyResults"><div className="brand"><span className="brandMark">⌁</span><span>Green Canopy</span></div><h1>No portfolio yet.</h1><p>Complete the investor questionnaire to create your educational simulation.</p><Link className="button" href="/">Build my portfolio</Link></main>;

  const topPriorities = Object.entries(portfolio.investor_profile.sustainability_priority_weights).filter(([, weight]) => weight > 0).sort((a,b) => b[1]-a[1]).map(([key]) => key.replaceAll("_"," "));
  return <main className="resultsPage">
    <nav className="resultsNav"><Link className="brand" href="/portfolio"><span className="brandMark">⌁</span><span>Green Canopy</span></Link><div className="navActions"><Link className="backButton navButton" href="/">Generate another</Link><Link className="button buttonSmall" href="/portfolio">Take me home</Link></div></nav>
    <header className="resultsHero"><div><span className="eyebrow">Your Green Canopy portfolio</span><h1>{portfolio.investor_profile.profile_name}</h1><p>{portfolio.investor_profile.profile_description} Your strongest priorities were {topPriorities.join(", ")}.</p></div><div className="heroScore"><span>Alignment</span><strong>{portfolio.sustainability_alignment_score}</strong><small>Green Canopy score · not “percent sustainable”</small></div></header>
    {portfolio.portfolio_narrative && <section className="resultsSection" style={{paddingBottom: 0}}><p className="resultNote" style={{fontSize: 14, padding: "20px 24px", maxWidth: 900}}>{portfolio.portfolio_narrative}</p></section>}
    <section className="metricGrid">
      <Metric label="Investment" value={money(portfolio.total_investment_amount)} note="Illustrative amount" />
      <Metric label="Historical annual return" value={pct(portfolio.annualized_historical_return)} note="Not a forecast" hint="Average yearly gain over the past 3 years. Past performance never guarantees future results." compare={portfolio.benchmark && `S&P 500: ${pct(portfolio.benchmark.annualized_historical_return)}`} />
      <Metric label="Historical volatility" value={pct(portfolio.annualized_volatility)} note="How bumpy the ride is" hint="How much the portfolio's value has swung year to year. Higher means a bumpier ride, not necessarily a worse outcome." compare={portfolio.benchmark && `S&P 500: ${pct(portfolio.benchmark.annualized_volatility)}`} />
      <Metric label="Maximum drawdown" value={pct(portfolio.maximum_drawdown)} note="Worst historical drop" hint="The biggest fall from a peak to a low point over the past 3 years — the worst-case dip you'd have lived through." compare={portfolio.benchmark && `S&P 500: ${pct(portfolio.benchmark.maximum_drawdown)}`} />
      <Metric label="Holdings" value={String(portfolio.number_of_holdings)} note="2% minimum position" />
      <Metric label="Diversification" value={`${portfolio.diversification_score}/100`} note="Spread across sectors" hint="Higher means your money is spread across more industries instead of concentrated in one — a form of risk reduction." />
    </section>
    <section className="resultsSection"><div className="resultsHeading"><div><span className="eyebrow">Allocation</span><h2>Why every holding belongs.</h2></div><div style={{textAlign: "right"}}><p style={{margin: 0}}>Weights total {portfolio.allocations.reduce((sum,item) => sum + item.weight, 0).toFixed(2)}% · Dollars total {money(portfolio.allocations.reduce((sum,item) => sum + item.dollar_amount, 0))}</p><button className="backButton navButton" style={{marginTop: 10}} onClick={() => downloadPortfolioCsv(portfolio)}>Download CSV</button></div></div>
      <div className="allocationTable">{portfolio.allocations.map((item) => <AllocationRow item={item} key={item.ticker} />)}</div>
    </section>
    <section className="resultsSplit">
      <div className="sectorPanel"><span className="eyebrow">Diversification</span><h2>Sector mix</h2>{Object.entries(portfolio.sector_distribution).sort((a,b) => b[1]-a[1]).map(([sector,value]) => <div className="sectorBar" key={sector}><span>{sector}</span><i><b style={{width:`${value}%`}} /></i><strong>{value.toFixed(1)}%</strong></div>)}</div>
      <div className="transparencyPanel"><span className="eyebrow lightEyebrow">Transparency</span><h2>What this result means.</h2><p>Data retrieved at {new Date(portfolio.data_retrieved_at).toLocaleString()}. <Link href="/methodology" style={{color:"#d8f1a5"}}>Read the full methodology →</Link></p>{portfolio.warnings.map((warning) => <p className="warning" key={warning}>{warning}</p>)}<ul>{portfolio.limitations.map((item) => <li key={item}>{item}</li>)}</ul><div className="glossary"><strong>What the numbers mean</strong><ul>{GLOSSARY.map(([term,def]) => <li key={term}><b>{term}:</b> {def}</li>)}</ul></div><small>Sources: {portfolio.sources.join(" · ")}</small></div>
    </section>
  </main>;
}

function Metric({label,value,note,hint,compare}:{label:string;value:string;note:string;hint?:string;compare?:string | null | false}) {
  return <div title={hint}><span>{label}</span><strong>{value}</strong><small>{note}</small>{compare && <small className="benchmarkNote">{compare}</small>}</div>;
}

const CONFIDENCE_HINT = "How strongly this holding matches your priorities. High: matches 2 or more. Medium: matches 1. Low: matches none.";

function AllocationRow({item}: {item: Allocation}) {
  const [open, setOpen] = useState(false);
  return <article className="allocationRow">
    <span className="tickerBadge">{item.ticker}</span>
    <div className="holdingIdentity"><strong>{item.name}</strong><small>{item.sector} · {item.asset_type.toUpperCase()}</small></div>
    <div><strong>{item.weight.toFixed(2)}%</strong><small>{money(item.dollar_amount)}</small></div>
    <div className="alignmentCell" title={CONFIDENCE_HINT}><strong>{item.alignment_score}/100</strong><small>{item.confidence} confidence</small></div>
    <p>
      {item.business_summary && <span className="businessBlurb">{item.business_summary}</span>}
      {item.why_selected} <WhyThis.Toggle open={open} onToggle={() => setOpen((value) => !value)} />
    </p>
    {open && <WhyThis.Panel detail={item.detail} />}
  </article>;
}
