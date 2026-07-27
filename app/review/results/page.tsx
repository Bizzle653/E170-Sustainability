"use client";

import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";
import { AlignmentDetail, WhyThis } from "@/components/WhyThis";
import { downloadCsv } from "@/lib/csv";

type Holding = {
  ticker: string;
  name: string;
  asset_type: string;
  sector: string;
  dollar_amount: number;
  weight: number;
  alignment_score: number;
  confidence: string;
  matched_priorities: string[];
  sustainability_status: string;
  in_green_canopy_universe: boolean;
  flag: string | null;
  detail: AlignmentDetail;
  business_summary: string | null;
};
type Suggestion = {
  ticker: string;
  name: string;
  asset_type: string;
  sector: string;
  alignment_score: number;
  matched_priorities: string[];
  why_suggested: string;
  detail: AlignmentDetail;
  business_summary: string | null;
};
type Benchmark = { ticker: string; name: string; annualized_historical_return: number; annualized_volatility: number; maximum_drawdown: number };
type Review = {
  investor_profile: { profile_name: string; profile_description: string; sustainability_priority_weights: Record<string, number> };
  total_value: number;
  holdings: Holding[];
  sustainability_alignment_score: number;
  portfolio_narrative: string;
  sector_distribution: Record<string, number>;
  diversification_score: number;
  annualized_historical_return: number | null;
  annualized_volatility: number | null;
  maximum_drawdown: number | null;
  benchmark: Benchmark | null;
  suggestions: Suggestion[];
  data_retrieved_at: string;
  sources: string[];
  warnings: string[];
  limitations: string[];
  excluded_holdings: { ticker: string; reason: string }[];
};

const money = (value: number) => value.toLocaleString("en-US", { style: "currency", currency: "USD" });
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
const GLOSSARY: [string, string][] = [
  ["Alignment score", "How well this holding matches the priorities you chose, on a 0-100 scale. It is not a percentage of anything."],
  ["Confidence", "How strongly a holding matches your priorities — high means 2 or more matches, medium means 1, low means none."],
  ["Diversification score", "Higher means your money is spread across more industries instead of concentrated in one."],
  ["Volatility", "How much your combined holdings have swung year to year historically. Higher is bumpier, not automatically worse."],
  ["Maximum drawdown", "The worst peak-to-low drop over the historical period shown — a sense of the roughest ride you'd have lived through."],
];
const CONFIDENCE_HINT = "How strongly this holding matches your priorities. High: matches 2 or more. Medium: matches 1. Low: matches none.";

function downloadReviewCsv(review: Review) {
  const headers = ["Section", "Ticker", "Name", "Type", "Sector", "Weight %", "Dollar Amount", "Alignment Score", "Matched Priorities", "Note"];
  const holdingRows = review.holdings.map((h) => [
    "Your holding", h.ticker, h.name, h.asset_type, h.sector, h.weight, h.dollar_amount, h.alignment_score, h.matched_priorities.join("; "), h.flag ?? "",
  ]);
  const suggestionRows = review.suggestions.map((s) => [
    "Suggestion", s.ticker, s.name, s.asset_type, s.sector, "", "", s.alignment_score, s.matched_priorities.join("; "), s.why_suggested,
  ]);
  downloadCsv(`green-canopy-review-${new Date().toISOString().slice(0, 10)}.csv`, headers, [...holdingRows, ...suggestionRows]);
}

export default function ReviewResultsPage() {
  const stored = useSyncExternalStore(
    () => () => undefined,
    () => sessionStorage.getItem("greenCanopyReview"),
    () => null,
  );
  const review = useMemo<Review | null>(() => (stored ? JSON.parse(stored) : null), [stored]);

  if (!review)
    return (
      <main className="emptyResults">
        <div className="brand">
          <span className="brandMark">⌁</span>
          <span>Green Canopy</span>
        </div>
        <h1>No review yet.</h1>
        <p>Tell us what you hold and what you care about to see how it lines up.</p>
        <Link className="button" href="/review">
          Review my holdings
        </Link>
      </main>
    );

  const topPriorities = Object.entries(review.investor_profile.sustainability_priority_weights)
    .filter(([, weight]) => weight > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([key]) => key.replaceAll("_", " "));

  return (
    <main className="resultsPage">
      <nav className="resultsNav">
        <Link className="brand" href="/">
          <span className="brandMark">⌁</span>
          <span>Green Canopy</span>
        </Link>
        <div className="navActions">
          <Link className="backButton navButton" href="/review">
            Review again
          </Link>
          <Link className="button buttonSmall" href="/">
            Take me home
          </Link>
        </div>
      </nav>

      <header className="resultsHero">
        <div>
          <span className="eyebrow">Your holdings review</span>
          <h1>Here&apos;s how your portfolio lines up.</h1>
          <p>
            {review.investor_profile.profile_description} Your strongest priorities were {topPriorities.join(", ")}.
          </p>
        </div>
        <div className="heroScore">
          <span>Alignment</span>
          <strong>{review.sustainability_alignment_score}</strong>
          <small>Green Canopy score · not “percent sustainable”</small>
        </div>
      </header>

      {review.portfolio_narrative && (
        <section className="resultsSection" style={{ paddingBottom: 0 }}>
          <p className="resultNote" style={{ fontSize: 14, padding: "20px 24px", maxWidth: 900 }}>{review.portfolio_narrative}</p>
        </section>
      )}

      <section className="metricGrid compact">
        <Metric label="Total reviewed" value={money(review.total_value)} note="Across matched holdings" />
        <Metric label="Holdings" value={String(review.holdings.length)} note="Successfully matched" />
        <Metric label="Diversification" value={`${review.diversification_score}/100`} note="Spread across sectors" hint="Higher means your money is spread across more industries instead of concentrated in one." />
        {review.annualized_historical_return != null && (
          <Metric label="Historical annual return" value={pct(review.annualized_historical_return)} note="Not a forecast" hint="Average yearly gain over the past 3 years, weighted by how much you hold of each. Past performance never guarantees future results." compare={review.benchmark && `S&P 500: ${pct(review.benchmark.annualized_historical_return)}`} />
        )}
        {review.annualized_volatility != null && (
          <Metric label="Historical volatility" value={pct(review.annualized_volatility)} note="How bumpy the ride is" hint="How much your combined holdings have swung year to year. Higher means a bumpier ride, not necessarily a worse outcome." compare={review.benchmark && `S&P 500: ${pct(review.benchmark.annualized_volatility)}`} />
        )}
        {review.maximum_drawdown != null && (
          <Metric label="Maximum drawdown" value={pct(review.maximum_drawdown)} note="Worst historical drop" hint="The biggest fall from a peak to a low point over the past 3 years — the worst-case dip you'd have lived through." compare={review.benchmark && `S&P 500: ${pct(review.benchmark.maximum_drawdown)}`} />
        )}
      </section>

      <section className="resultsSection">
        <div className="resultsHeading">
          <div>
            <span className="eyebrow">Your holdings</span>
            <h2>What you already own.</h2>
          </div>
          <div style={{ textAlign: "right" }}>
            <p style={{ margin: 0 }}>Weights total {review.holdings.reduce((sum, item) => sum + item.weight, 0).toFixed(2)}%</p>
            <button className="backButton navButton" style={{ marginTop: 10 }} onClick={() => downloadReviewCsv(review)}>Download CSV</button>
          </div>
        </div>
        <div className="allocationTable">
          {review.holdings.map((item) => (
            <HoldingRow item={item} key={item.ticker} />
          ))}
        </div>
        {review.excluded_holdings.length > 0 && (
          <p className="resultNote" style={{ marginTop: 16 }}>
            Couldn&apos;t retrieve data for: {review.excluded_holdings.map((item) => item.ticker).join(", ")}.
          </p>
        )}
      </section>

      {review.suggestions.length > 0 && (
        <section className="resultsSection">
          <div className="resultsHeading">
            <div>
              <span className="eyebrow">Suggestions</span>
              <h2>A few things you might be missing.</h2>
            </div>
          </div>
          <div className="allocationTable">
            {review.suggestions.map((item) => (
              <SuggestionRow item={item} key={item.ticker} />
            ))}
          </div>
        </section>
      )}

      <section className="resultsSplit">
        <div className="sectorPanel">
          <span className="eyebrow">Diversification</span>
          <h2>Sector mix</h2>
          {Object.entries(review.sector_distribution)
            .sort((a, b) => b[1] - a[1])
            .map(([sector, value]) => (
              <div className="sectorBar" key={sector}>
                <span>{sector}</span>
                <i>
                  <b style={{ width: `${value}%` }} />
                </i>
                <strong>{value.toFixed(1)}%</strong>
              </div>
            ))}
        </div>
        <div className="transparencyPanel">
          <span className="eyebrow lightEyebrow">Transparency</span>
          <h2>What this result means.</h2>
          <p>Data retrieved at {new Date(review.data_retrieved_at).toLocaleString()}. <Link href="/methodology" style={{color:"#d8f1a5"}}>Read the full methodology →</Link></p>
          {review.warnings.map((warning) => (
            <p className="warning" key={warning}>
              {warning}
            </p>
          ))}
          <ul>
            {review.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div className="glossary">
            <strong>What the numbers mean</strong>
            <ul>
              {GLOSSARY.map(([term, def]) => (
                <li key={term}>
                  <b>{term}:</b> {def}
                </li>
              ))}
            </ul>
          </div>
          <small>Sources: {review.sources.join(" · ")}</small>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value, note, hint, compare }: { label: string; value: string; note: string; hint?: string; compare?: string | null | false }) {
  return (
    <div title={hint}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
      {compare && <small className="benchmarkNote">{compare}</small>}
    </div>
  );
}

function HoldingRow({ item }: { item: Holding }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="allocationRow">
      <span className="tickerBadge">{item.ticker}</span>
      <div className="holdingIdentity">
        <strong>{item.name}</strong>
        <small>
          {item.sector} · {item.asset_type.toUpperCase()}
        </small>
      </div>
      <div>
        <strong>{item.weight.toFixed(2)}%</strong>
        <small>{money(item.dollar_amount)}</small>
      </div>
      <div className="alignmentCell" title={CONFIDENCE_HINT}>
        <strong>{item.alignment_score}/100</strong>
        <small>{item.confidence} confidence</small>
      </div>
      <p>
        {item.business_summary && <span className="businessBlurb">{item.business_summary}</span>}
        {item.flag ? (
          <span className="warning">{item.flag}</span>
        ) : item.matched_priorities.length ? (
          `Supports ${item.matched_priorities.join(", ")}.`
        ) : (
          "Meets your financial-data requirements."
        )}
        {!item.in_green_canopy_universe && " Outside Green Canopy's tracked universe."}{" "}
        <WhyThis.Toggle open={open} onToggle={() => setOpen((value) => !value)} />
      </p>
      {open && <WhyThis.Panel detail={item.detail} />}
    </article>
  );
}

function SuggestionRow({ item }: { item: Suggestion }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="allocationRow">
      <span className="tickerBadge">{item.ticker}</span>
      <div className="holdingIdentity">
        <strong>{item.name}</strong>
        <small>
          {item.sector} · {item.asset_type.toUpperCase()}
        </small>
      </div>
      <div>
        <strong>—</strong>
        <small>Not currently held</small>
      </div>
      <div className="alignmentCell">
        <strong>{item.alignment_score}/100</strong>
        <small>alignment score</small>
      </div>
      <p>
        {item.business_summary && <span className="businessBlurb">{item.business_summary}</span>}
        {item.why_suggested} <WhyThis.Toggle open={open} onToggle={() => setOpen((value) => !value)} />
      </p>
      {open && <WhyThis.Panel detail={item.detail} />}
    </article>
  );
}
