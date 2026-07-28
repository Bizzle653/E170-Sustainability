"use client";

import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";

const CATEGORIES = [
  ["Climate", "Emissions, decarbonization, low-carbon energy"],
  ["Clean energy", "Solar, wind, geothermal, battery storage"],
  ["Fair work", "Workplace safety, fair wages, collective bargaining"],
  ["Human rights", "Forced labor, ethical and responsible sourcing"],
  ["Nature", "Biodiversity, habitat and ecosystem conservation"],
  ["Water", "Conservation, treatment, watershed protection"],
  ["Agriculture", "Sustainable and regenerative farming"],
  ["Circularity", "Recycling, waste reduction, packaging"],
  ["Governance", "Board oversight, ethics, anti-corruption"],
];

const STEPS: [string, string, string][] = [
  ["01", "You answer a questionnaire", "Priorities, exclusions, timeline, risk comfort, and how much return you're willing to trade off for values-alignment. This becomes a deterministic investor profile — the same answers always produce the same profile."],
  ["02", "Securities get scored against your profile", "Every stock or fund's Green Canopy classification tags are compared against your selected priorities. A security's alignment score also factors in a small diversification credit for funds, and third-party ESG data when available."],
  ["03", "Financial performance enters the picture", "Candidate selection blends each security's historical risk-adjusted return with its alignment score, weighted by how much trade-off you said you'd accept. Values-alignment always keeps at least a strong plurality of the weight."],
  ["04", "A constrained optimizer picks weights", "Among your chosen holdings, a SciPy optimizer balances expected return, historical risk, and alignment score to decide how much of each to hold, subject to your maximum concentration per position."],
];

export default function MethodologyPage() {
  return (
    <main className="resultsPage">
      <SiteNav />

      <header className="resultsHero">
        <div>
          <span className="eyebrow">Methodology</span>
          <h1>How Green Canopy actually works.</h1>
          <p>
            No black boxes. This page explains, in plain terms, exactly how a questionnaire becomes a portfolio,
            how a company earns a tag, and what the numbers on your results page really mean — including where
            the system is genuinely limited.
          </p>
        </div>
      </header>

      <section className="resultsSection">
        <div className="resultsHeading">
          <div>
            <span className="eyebrow">The pipeline</span>
            <h2>From your answers to a portfolio.</h2>
          </div>
        </div>
        <div className="steps">
          {STEPS.map(([number, title, copy]) => (
            <article className="stepCard" key={number}>
              <span className="stepNumber">{number}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="resultsSection">
        <div className="resultsHeading">
          <div>
            <span className="eyebrow">Classification</span>
            <h2>How a company earns a tag.</h2>
          </div>
        </div>
        <p style={{maxWidth: 760, color: "var(--muted)", lineHeight: 1.7, marginBottom: 24}}>
          Every security can be tagged into up to 9 categories. A tag is only ever assigned when it can point to a
          real sentence from the company&apos;s own public business description — never guessed from its sector
          alone, and never invented. That evidence is the same text you can see by clicking &quot;Why this?&quot;
          on any holding.
        </p>
        <div className="priorityChecklist" style={{marginBottom: 16}}>
          {CATEGORIES.map(([label, desc]) => (
            <span className="matched" key={label} title={desc}>{label}</span>
          ))}
        </div>
        <p style={{maxWidth: 760, marginBottom: 24}}>
          <Link href="/learn" style={{fontWeight: 800, color: "var(--forest-2)"}}>What do these categories actually mean? →</Link>
        </p>
        <p style={{maxWidth: 760, color: "var(--muted)", lineHeight: 1.7}}>
          Coverage is honest, not complete: as of this writing, 113 of 955 tracked companies (about 12%) have at
          least one tag. The rest simply don&apos;t mention any of these 9 categories explicitly in their business
          description — an untagged company isn&apos;t being penalized, there just wasn&apos;t textual evidence to
          responsibly tag it from. Coverage grows over time as the classification process is re-run.
        </p>
      </section>

      <section className="resultsSection">
        <div className="resultsHeading">
          <div>
            <span className="eyebrow">Scoring</span>
            <h2>What the alignment score means.</h2>
          </div>
        </div>
        <div className="allocationTable">
          <article className="allocationRow" style={{gridTemplateColumns: "1fr"}}>
            <p style={{margin: 0, color: "var(--muted)", lineHeight: 1.8, fontSize: 13}}>
              Every alignment score starts at a base of 25, then adds points for each of your selected priorities the
              security is tagged for (weighted by how strongly you prioritized it — your first choice counts more
              than your third), plus a small credit for funds since they spread risk across many holdings. If
              third-party ESG risk data happens to be available for that security, it nudges the score slightly
              further. The result is capped to a 0–100 scale. <strong>It is not a percentage of anything</strong> —
              it&apos;s a relative measure of fit between this specific security and your specific priorities.
            </p>
          </article>
        </div>
      </section>

      <section className="resultsSplit">
        <div className="sectorPanel">
          <span className="eyebrow">Confidence</span>
          <h2>High, medium, low.</h2>
          <p style={{color: "var(--muted)", fontSize: 13, lineHeight: 1.7, marginBottom: 12}}>
            Confidence reflects how many of your selected priorities a holding actually matches — not how
            &quot;good&quot; it is.
          </p>
          <div className="priorityChecklist">
            <span className="matched">High — matches 2+ priorities</span>
            <span className="matched">Medium — matches 1 priority</span>
            <span className="unmatched">Low — matches none</span>
          </div>
        </div>
        <div className="transparencyPanel">
          <span className="eyebrow lightEyebrow">Limitations</span>
          <h2>What this isn&apos;t.</h2>
          <ul>
            <li>This is an educational simulation. It does not connect to a brokerage and does not execute trades.</li>
            <li>Historical returns, volatility, and drawdown are descriptive of the past 3 years — never a forecast or guarantee.</li>
            <li>Yahoo Finance discontinued its free ESG data endpoint industry-wide, so third-party ESG scoring is currently unavailable for every security. Alignment scores rely on Green Canopy&apos;s own classification tags instead.</li>
            <li>The S&amp;P 500 (SPY) benchmark shown alongside your results is a general market reference, not a personalized recommendation or a claim that it&apos;s the &quot;right&quot; comparison for your goals.</li>
            <li>Nothing here is financial advice. This is a values-alignment and education tool, not a substitute for professional guidance.</li>
          </ul>
          <small>Sources: Yahoo Finance via yfinance · Green Canopy classification metadata</small>
        </div>
      </section>
    </main>
  );
}
