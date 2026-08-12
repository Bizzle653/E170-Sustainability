"use client";

import { useEffect, useState } from "react";
import { SiteNav } from "@/components/SiteNav";
import { apiUrl } from "@/lib/api";

type AgentStatus = {
  agent: string;
  policy_version: string;
  prompt_version: string;
  total_securities: number;
  verified_securities: number;
  checked_securities: number;
  pending_securities: number;
  coverage_percent: number;
  retry_count: number;
  retry_queue: Array<{ticker: string; failure_count: number; next_retry_at?: string}>;
  last_run?: {
    completed_at?: string;
    status?: string;
    selected?: number;
    succeeded?: number;
    changed?: number;
    failed?: number;
  } | null;
};

export function AgentStatusContent() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch(apiUrl("/api/agent/status"), {signal: controller.signal})
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(setStatus)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setError(requestError instanceof Error ? requestError.message : "Status could not be loaded");
      });
    return () => controller.abort();
  }, []);

  return (
    <>
      <section className="classificationHero">
        <span className="eyebrow">Autonomous Agent operations</span>
        <h1>Classification coverage is measurable.</h1>
        <p>
          This page distinguishes legacy metadata from labels that the Agent has checked against exact source
          quotations. Failures are retried automatically and do not block successful classifications.
        </p>
      </section>
      <section className="classificationFeed">
        {error && <div className="classificationEmpty">Agent status could not be loaded ({error}).</div>}
        {!status && !error && <div className="classificationEmpty">Loading Agent status…</div>}
        {status && (
          <>
            <article className="classificationNotice">
              <header><div><span className="tickerBadge">{status.coverage_percent}%</span><div>
                <strong>{status.verified_securities} of {status.total_securities} securities verified</strong>
                <small>{status.pending_securities} still require an evidence-backed Agent review</small>
              </div></div></header>
              <div className="agentProgress" aria-label={`${status.coverage_percent}% verified`}>
                <span style={{width: `${status.coverage_percent}%`}} />
              </div>
              <p className="classificationSummary">
                Unreviewed and stale labels receive reduced scoring weight and cannot be presented with high confidence.
              </p>
            </article>
            <article className="classificationNotice">
              <header><div><span className="tickerBadge">RUN</span><div>
                <strong>Latest autonomous run: {status.last_run?.status ?? "not available"}</strong>
                <small>{status.last_run?.completed_at ? new Date(status.last_run.completed_at).toLocaleString() : "No completed run recorded"}</small>
              </div></div></header>
              <p className="classificationSummary">
                Selected {status.last_run?.selected ?? 0}; succeeded {status.last_run?.succeeded ?? 0}; changed {status.last_run?.changed ?? 0}; failed {status.last_run?.failed ?? 0}.
              </p>
              <small>Policy {status.policy_version} · prompt {status.prompt_version}</small>
            </article>
            <article className="classificationNotice">
              <header><div><span className="tickerBadge">{status.retry_count}</span><div>
                <strong>Automatic retry queue</strong><small>Transient data-source failures use bounded backoff.</small>
              </div></div></header>
              {status.retry_queue.length === 0 ? <p className="classificationSummary">No securities are waiting for retry.</p> : (
                <ul className="evidenceList">{status.retry_queue.map((item) => (
                  <li key={item.ticker}>{item.ticker}: attempt {item.failure_count}; next retry {item.next_retry_at ? new Date(item.next_retry_at).toLocaleString() : "next run"}</li>
                ))}</ul>
              )}
            </article>
          </>
        )}
      </section>
    </>
  );
}

export default function AgentStatusPage() {
  return (
    <main className="classificationPage">
      <SiteNav />
      <AgentStatusContent />
    </main>
  );
}
