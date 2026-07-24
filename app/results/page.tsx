"use client";

import Link from "next/link";
import { useMemo, useSyncExternalStore } from "react";

type Allocation = {
  ticker: string; name: string; asset_type: string; sector: string; weight: number;
  dollar_amount: number; alignment_score: number; confidence: string;
  matched_priorities: string[]; why_selected: string; sustainability_status: string;
};
type Portfolio = {
  investor_profile: {profile_name: string; profile_description: string; risk_score: number; sustainability_priority_weights: Record<string, number>};
  total_investment_amount: number; allocations: Allocation[]; sustainability_alignment_score: number;
  annualized_historical_return: number; annualized_volatility: number; maximum_drawdown: number;
  number_of_holdings: number; sector_distribution: Record<string, number>; diversification_score: number;
  data_retrieved_at: string; sources: string[]; warnings: string[]; limitations: string[];
};

const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
const money = (value: number) => value.toLocaleString("en-US", {style: "currency", currency: "USD"});

export default function ResultsPage() {
  const stored = useSyncExternalStore(
    () => () => undefined,
    () => sessionStorage.getItem("greenCanopyPortfolio"),
    () => null,
  );
  const portfolio = useMemo<Portfolio | null>(() => stored ? JSON.parse(stored) : null, [stored]);

  if (!portfolio) return <main className="emptyResults"><div className="brand"><span className="brandMark">⌁</span><span>Green Canopy</span></div><h1>No portfolio yet.</h1><p>Complete the investor questionnaire to create your educational simulation.</p><Link className="button" href="/">Build my portfolio</Link></main>;

  const topPriorities = Object.entries(portfolio.investor_profile.sustainability_priority_weights).filter(([, weight]) => weight > 0).sort((a,b) => b[1]-a[1]).map(([key]) => key.replaceAll("_"," "));
  return <main className="resultsPage">
    <nav className="resultsNav"><Link className="brand" href="/"><span className="brandMark">⌁</span><span>Green Canopy</span></Link><Link className="button buttonSmall" href="/">Build another</Link></nav>
    <header className="resultsHero"><div><span className="eyebrow">Your Green Canopy portfolio</span><h1>{portfolio.investor_profile.profile_name}</h1><p>{portfolio.investor_profile.profile_description} Your strongest priorities were {topPriorities.join(", ")}.</p></div><div className="heroScore"><span>Alignment</span><strong>{portfolio.sustainability_alignment_score}</strong><small>Green Canopy score · not “percent sustainable”</small></div></header>
    <section className="metricGrid">
      <Metric label="Investment" value={money(portfolio.total_investment_amount)} note="Illustrative amount" />
      <Metric label="Historical annual return" value={pct(portfolio.annualized_historical_return)} note="Not a forecast" />
      <Metric label="Historical volatility" value={pct(portfolio.annualized_volatility)} note="Annualized" />
      <Metric label="Maximum drawdown" value={pct(portfolio.maximum_drawdown)} note="Observed period" />
      <Metric label="Holdings" value={String(portfolio.number_of_holdings)} note="2% minimum position" />
      <Metric label="Diversification" value={`${portfolio.diversification_score}/100`} note="Sector concentration" />
    </section>
    <section className="resultsSection"><div className="resultsHeading"><div><span className="eyebrow">Allocation</span><h2>Why every holding belongs.</h2></div><p>Weights total {portfolio.allocations.reduce((sum,item) => sum + item.weight, 0).toFixed(2)}% · Dollars total {money(portfolio.allocations.reduce((sum,item) => sum + item.dollar_amount, 0))}</p></div>
      <div className="allocationTable">{portfolio.allocations.map((item) => <article className="allocationRow" key={item.ticker}><span className="tickerBadge">{item.ticker}</span><div className="holdingIdentity"><strong>{item.name}</strong><small>{item.sector} · {item.asset_type.toUpperCase()}</small></div><div><strong>{item.weight.toFixed(2)}%</strong><small>{money(item.dollar_amount)}</small></div><div className="alignmentCell"><strong>{item.alignment_score}/100</strong><small>{item.confidence} confidence · ESG data {item.sustainability_status}</small></div><p>{item.why_selected}</p></article>)}</div>
    </section>
    <section className="resultsSplit">
      <div className="sectorPanel"><span className="eyebrow">Diversification</span><h2>Sector mix</h2>{Object.entries(portfolio.sector_distribution).sort((a,b) => b[1]-a[1]).map(([sector,value]) => <div className="sectorBar" key={sector}><span>{sector}</span><i><b style={{width:`${value}%`}} /></i><strong>{value.toFixed(1)}%</strong></div>)}</div>
      <div className="transparencyPanel"><span className="eyebrow lightEyebrow">Transparency</span><h2>What this result means.</h2><p>Data retrieved at {new Date(portfolio.data_retrieved_at).toLocaleString()}.</p>{portfolio.warnings.map((warning) => <p className="warning" key={warning}>{warning}</p>)}<ul>{portfolio.limitations.map((item) => <li key={item}>{item}</li>)}</ul><small>Sources: {portfolio.sources.join(" · ")}</small></div>
    </section>
  </main>;
}

function Metric({label,value,note}:{label:string;value:string;note:string}) {
  return <div><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}
