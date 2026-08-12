"use client";

import { useEffect, useState } from "react";
import { SiteNav } from "@/components/SiteNav";
import { apiUrl } from "@/lib/api";

type Evidence = {
  id: string;
  kind: string;
  title: string;
  source: string;
  retrieved_at: string;
  published_at?: string | null;
  url?: string | null;
  excerpt: string;
};

type ClassificationUpdate = {
  id: string;
  ticker: string;
  name: string;
  asset_type: string;
  published_at: string;
  model: string;
  policy_version?: string | null;
  prompt_version?: string | null;
  verification?: string | null;
  added_tags: string[];
  removed_tags: string[];
  added_exclusions: string[];
  removed_exclusions: string[];
  summary: string;
  confidence: number;
  evidence: Evidence[];
  greenwashing_flags: string[];
  evidence_limitations?: string[];
  portfolio_impact: string;
};

const label = (value: string) => value.replaceAll("_", " ");

export function ClassificationUpdatesContent() {
  const [updates, setUpdates] = useState<ClassificationUpdate[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [portfolioTickers, setPortfolioTickers] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const portfolioTimer = window.setTimeout(() => {
      try {
        const raw = localStorage.getItem("greenCanopyPortfolio") ?? sessionStorage.getItem("greenCanopyPortfolio");
        const portfolio = raw ? JSON.parse(raw) : null;
        const tickers = Array.isArray(portfolio?.allocations)
          ? portfolio.allocations.map((holding: {ticker?: string}) => holding.ticker).filter(Boolean)
          : [];
        setPortfolioTickers(tickers);
      } catch {
        setPortfolioTickers([]);
      }
    }, 0);
    fetch(apiUrl("/api/classifications/updates?limit=100"), { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        setUpdates(payload.updates ?? []);
        setTotal(payload.total ?? 0);
        setNextOffset(payload.next_offset ?? null);
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setError(requestError instanceof Error ? requestError.message : "Updates could not be loaded");
      })
      .finally(() => setLoading(false));
    return () => {
      controller.abort();
      window.clearTimeout(portfolioTimer);
    };
  }, []);

  async function loadMore() {
    if (nextOffset === null || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/classifications/updates?limit=100&offset=${nextOffset}`));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      setUpdates((current) => [...current, ...(payload.updates ?? [])]);
      setTotal(payload.total ?? total);
      setNextOffset(payload.next_offset ?? null);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Updates could not be loaded");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <section className="classificationHero">
        <span className="eyebrow">Autonomous AI classification</span>
        <h1>Every label change is public.</h1>
        <p>
          Green Canopy&apos;s Sustainability Intelligence Agent researches companies and funds, updates internal
          classification metadata when cited evidence clears its confidence threshold, and publishes the reason here.
          These labels are Green Canopy metadata—not third-party ESG ratings or investment advice.
        </p>
      </section>

      <section className="classificationFeed">
        {loading && <div className="classificationEmpty">Loading classification announcements…</div>}
        {error && <div className="classificationEmpty">Announcements could not be loaded ({error}).</div>}
        {!loading && !error && updates.length === 0 && (
          <div className="classificationEmpty">
            <strong>No classification changes have been published yet.</strong>
            <p>The feed will populate after the autonomous research workflow makes its first evidence-backed change.</p>
          </div>
        )}

        {updates.map((update) => (
          <article className="classificationNotice" key={update.id}>
            <header>
              <div>
                <span className="tickerBadge">{update.ticker}</span>
                <div>
                  <strong>{update.name}</strong>
                  <small>{update.asset_type.toUpperCase()} · {new Date(update.published_at).toLocaleString()}</small>
                </div>
              </div>
              <span className="confidenceBadge">{Math.round(update.confidence * 100)}% confidence</span>
            </header>

            <div className="classificationChanges">
              {update.added_tags.map((tag) => <span className="added" key={`add-${tag}`}>+ {label(tag)}</span>)}
              {update.removed_tags.map((tag) => <span className="removed" key={`remove-${tag}`}>− {label(tag)}</span>)}
              {update.added_exclusions.map((tag) => <span className="warning" key={`exclude-${tag}`}>+ exclusion: {label(tag)}</span>)}
              {update.removed_exclusions.map((tag) => <span className="removed" key={`allow-${tag}`}>− exclusion: {label(tag)}</span>)}
            </div>

            <p className="classificationSummary">{update.summary}</p>

            {portfolioTickers.includes(update.ticker) && (
              <p className="portfolioAffected">
                Your saved Green Canopy portfolio contains {update.ticker}. Its displayed alignment score may change
                when the portfolio is regenerated or reviewed; the Agent has not changed your allocation.
              </p>
            )}

            {update.greenwashing_flags.length > 0 && (
              <div className="classificationFlags">
                <strong>Claim conflicts detected</strong>
                <ul>{update.greenwashing_flags.map((flag) => <li key={flag}>{flag}</li>)}</ul>
              </div>
            )}

            <details>
              <summary>View evidence and limitations</summary>
              <div className="classificationEvidence">
                {update.evidence.map((source) => (
                  <div key={`${update.id}-${source.id}`}>
                    <strong>{source.title}</strong>
                    <small>
                      {source.source}
                      {source.published_at ? ` · published ${new Date(source.published_at).toLocaleDateString()}` : ""}
                      {` · retrieved ${new Date(source.retrieved_at).toLocaleDateString()}`}
                    </small>
                    <p>{source.excerpt}</p>
                    {source.url && <a className="textLink" href={source.url} target="_blank" rel="noreferrer">Open source</a>}
                  </div>
                ))}
                {(update.evidence_limitations ?? []).map((limitation) => (
                  <p className="classificationImpact" key={limitation}>{limitation}</p>
                ))}
                <p className="classificationImpact">{update.portfolio_impact}</p>
                <small>
                  Model: {update.model}
                  {update.policy_version ? ` · policy ${update.policy_version}` : ""}
                  {update.prompt_version ? ` · prompt ${update.prompt_version}` : ""}
                  {update.verification ? ` · ${label(update.verification)}` : ""}
                </small>
              </div>
            </details>
          </article>
        ))}
        {nextOffset !== null && (
          <button className="button" type="button" onClick={loadMore} disabled={loading}>
            {loading ? "Loading…" : `Load older announcements (${updates.length} of ${total})`}
          </button>
        )}
      </section>
    </>
  );
}

export default function ClassificationUpdatesPage() {
  return (
    <main className="classificationPage">
      <SiteNav />
      <ClassificationUpdatesContent />
    </main>
  );
}
