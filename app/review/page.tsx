"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SiteNav } from "@/components/SiteNav";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

const priorities = [
  ["climate", "Climate", "Lower carbon emissions"],
  ["renewable_energy", "Clean energy", "Renewables and storage"],
  ["fair_labor", "Fair work", "Labor rights and safe workplaces"],
  ["human_rights", "Human rights", "Forced-labor avoidance"],
  ["biodiversity", "Nature", "Biodiversity and ecosystems"],
  ["clean_water", "Water", "Access, quality, and efficiency"],
  ["sustainable_agriculture", "Agriculture", "Resilient food systems"],
  ["circular_economy", "Circularity", "Waste and materials"],
  ["governance", "Governance", "Leadership and accountability"],
];
const exclusions = [
  ["fossil_fuels", "Fossil fuels"],
  ["tobacco", "Tobacco"],
  ["weapons", "Weapons"],
  ["gambling", "Gambling"],
  ["severe_labor_controversies", "Severe labor controversies"],
  ["severe_environmental_controversies", "Severe environmental controversies"],
];

type Row = { ticker: string; amount: string };

export default function ReviewPage() {
  const router = useRouter();
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>(["climate"]);
  const [selectedExclusions, setSelectedExclusions] = useState<string[]>([]);
  const [rows, setRows] = useState<Row[]>([
    { ticker: "", amount: "" },
    { ticker: "", amount: "" },
    { ticker: "", amount: "" },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function togglePriority(key: string) {
    setSelectedPriorities((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : current.length < 3
        ? [...current, key]
        : current,
    );
  }

  function toggleExclusion(key: string) {
    setSelectedExclusions((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  }

  function updateRow(index: number, field: keyof Row, value: string) {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  function addRow() {
    setRows((current) => [...current, { ticker: "", amount: "" }]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, i) => i !== index));
  }

  const validRows = rows.filter((row) => row.ticker.trim() && Number(row.amount) > 0);
  const canSubmit = validRows.length > 0 && selectedPriorities.length > 0 && !loading;

  async function submit() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/portfolio/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          holdings: validRows.map((row) => ({
            ticker: row.ticker.trim().toUpperCase(),
            dollar_amount: Number(row.amount),
          })),
          answers: {
            priorities: selectedPriorities,
            exclusions: selectedExclusions,
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "We could not analyze your holdings.");
      sessionStorage.setItem("greenCanopyReview", JSON.stringify(payload));
      router.push("/review/results");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not analyze your holdings.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="resultsPage">
      <SiteNav />

      <header className="resultsHero">
        <div>
          <span className="eyebrow">Review your holdings</span>
          <h1>See how what you already own lines up with what you care about.</h1>
          <p>
            Tell us what matters to you and what you currently hold. We&apos;ll score each holding against your
            priorities and suggest a few things you might be missing—no brokerage connection required.
          </p>
        </div>
      </header>

      <section className="resultsSection">
        <div className="resultsHeading">
          <div>
            <span className="eyebrow">Step 1</span>
            <h2>What matters most to you?</h2>
          </div>
          <p>Choose up to three. {selectedPriorities.length}/3 selected.</p>
        </div>
        <div className="choiceGrid">
          {priorities.map(([key, title, copy]) => (
            <button
              className={`choiceCard ${selectedPriorities.includes(key) ? "selected" : ""}`}
              onClick={() => togglePriority(key)}
              key={key}
            >
              <span>{selectedPriorities.includes(key) ? "✓" : "+"}</span>
              <strong>{title}</strong>
              <small>{copy}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="resultsSection">
        <div className="resultsHeading">
          <div>
            <span className="eyebrow">Step 2 (optional)</span>
            <h2>Anything you&apos;d rather avoid?</h2>
          </div>
        </div>
        <div className="choiceGrid">
          {exclusions.map(([key, title]) => (
            <button
              className={`choiceCard compact ${selectedExclusions.includes(key) ? "selected" : ""}`}
              onClick={() => toggleExclusion(key)}
              key={key}
            >
              <span>{selectedExclusions.includes(key) ? "✓" : "+"}</span>
              <strong>{title}</strong>
              <small>Flag if held, exclude from suggestions</small>
            </button>
          ))}
        </div>
      </section>

      <section className="resultsSection">
        <div className="resultsHeading">
          <div>
            <span className="eyebrow">Step 3</span>
            <h2>What do you currently own?</h2>
          </div>
          <p>Ticker symbol and roughly how much you have in it. Estimates are fine.</p>
        </div>
        <div className="holdingInputs">
          {rows.map((row, index) => (
            <div className="holdingInputRow" key={index}>
              <input
                aria-label="Ticker symbol"
                placeholder="e.g. AAPL"
                value={row.ticker}
                maxLength={10}
                onChange={(event) => updateRow(index, "ticker", event.target.value)}
              />
              <div className="holdingAmountField">
                <span>$</span>
                <input
                  aria-label="Dollar amount"
                  type="number"
                  min="0"
                  placeholder="Amount"
                  value={row.amount}
                  onChange={(event) => updateRow(index, "amount", event.target.value)}
                />
              </div>
              <button
                className="removeRowButton"
                aria-label="Remove holding"
                onClick={() => removeRow(index)}
                disabled={rows.length <= 1}
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <button className="backButton addRowButton" onClick={addRow}>
          + Add another holding
        </button>

        {error && (
          <p className="errorMessage" role="alert">
            {error}
          </p>
        )}

        <div className="builderActions">
          <span />
          <button className="button" disabled={!canSubmit} onClick={submit}>
            {loading ? "Analyzing…" : "Review my holdings"} <span>→</span>
          </button>
        </div>
      </section>
    </main>
  );
}
