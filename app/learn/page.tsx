"use client";

import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";

type Category = {
  label: string;
  looksLike: string;
  whyItMatters: string;
  signal: string;
};

const CATEGORIES: Category[] = [
  {
    label: "Climate",
    looksLike: "Reducing greenhouse gas emissions, setting decarbonization targets, or supporting the shift to a lower-carbon economy — from utilities retiring coal plants to industrials investing in carbon capture.",
    whyItMatters: "Climate change is reshaping how businesses operate and how they're regulated. Companies unprepared for a lower-carbon future face transition risk — stranded assets, new carbon costs, tightening emissions rules — while others sit on real opportunity in the shift itself.",
    signal: "A utility describing its actual generating capacity as including nuclear, wind, and solar is a concrete signal. A company saying it's \"committed to sustainability\" with no specifics isn't.",
  },
  {
    label: "Clean energy",
    looksLike: "Producing or enabling solar, wind, geothermal, or hydroelectric power — or the battery storage that makes renewables usable at grid scale.",
    whyItMatters: "The energy transition is one of the largest capital reallocations happening in markets right now. Companies with real generation or manufacturing exposure sit closer to that shift than companies that only reference it in passing.",
    signal: "Look for actual megawatts of capacity, installed base, or component manufacturing volume — not just aspirational language about \"clean energy leadership.\"",
  },
  {
    label: "Fair work",
    looksLike: "Workplace safety programs, fair wage commitments, collective bargaining relationships, and structured employee training.",
    whyItMatters: "Labor practices are a leading indicator of operational risk. Companies with poor labor relations face strikes, high turnover, regulatory penalties, and reputational damage that eventually shows up in earnings.",
    signal: "Specific safety programs or named bargaining agreements are real signals. \"Our people are our greatest asset\" on its own is not.",
  },
  {
    label: "Human rights",
    looksLike: "Preventing forced or child labor across a supply chain, ethical sourcing standards, and human rights due diligence on suppliers.",
    whyItMatters: "Supply chain scandals create acute legal, regulatory, and brand risk — and disclosure requirements around this are tightening in major markets.",
    signal: "Specific supplier audit programs or sourcing standards count. Generic \"we value human rights\" statements don't tell you much.",
  },
  {
    label: "Nature",
    looksLike: "Habitat conservation, certified sustainable forestry, biodiversity impact assessments, and avoiding deforestation.",
    whyItMatters: "Businesses that depend on natural resources — timber, agriculture, extractives — carry real long-term risk if those resources are degraded or become more strictly regulated.",
    signal: "\"Manages 100% of timberlands on a fully sustainable basis in compliance with internationally recognized standards\" is concrete. Vague nature-appreciation language is not.",
  },
  {
    label: "Water",
    looksLike: "Water conservation programs, wastewater treatment investment, watershed protection, and water-efficient operations.",
    whyItMatters: "Water scarcity is a growing operational risk across manufacturing, agriculture, and energy — and an increasing regulatory focus in water-stressed regions.",
    signal: "Named treatment infrastructure or conservation targets are real signals. \"We care about water\" is not.",
  },
  {
    label: "Agriculture",
    looksLike: "Regenerative farming practices, soil health programs, and sustainable sourcing of agricultural commodities.",
    whyItMatters: "Agriculture sits at the intersection of food security, climate, and land use. Companies managing this well are better positioned for a more resource-constrained future.",
    signal: "Specific sourcing standards tied to actual agricultural operations matter more than general sustainability branding on food products.",
  },
  {
    label: "Circularity",
    looksLike: "Recycling programs, waste reduction targets, reduced or recyclable packaging, and materials recovery.",
    whyItMatters: "Circular practices often reduce material costs and regulatory exposure (like packaging waste rules) while cutting environmental footprint — one of the few categories where the business case and the impact case usually point the same direction.",
    signal: "Concrete recycling or packaging commitments count. General \"sustainability\" language without a program behind it doesn't.",
  },
  {
    label: "Governance",
    looksLike: "Independent board oversight, executive compensation tied to performance, anti-corruption policies, and whistleblower protections.",
    whyItMatters: "Governance is often the best predictor of whether a company's other sustainability claims hold up over time. Well-governed companies are less prone to fraud, scandal, and the kind of surprises that erase shareholder value overnight.",
    signal: "Specific board structure or compliance program details are real signals. \"We value integrity\" on its own is not.",
  },
];

export default function LearnPage() {
  return (
    <main className="resultsPage">
      <SiteNav />

      <header className="resultsHero">
        <div>
          <span className="eyebrow">Learn</span>
          <h1>What each category actually means.</h1>
          <p>
            Green Canopy&apos;s 9 classification categories aren&apos;t abstract labels. Each one reflects a real, specific
            kind of corporate behavior — and each one has a real reason it matters to a values-driven investor. This
            page explains what to actually look for, not just what the tag is called.
          </p>
        </div>
      </header>

      <section className="resultsSection">
        <div className="learnGrid">
          {CATEGORIES.map((category) => (
            <article className="learnCard" key={category.label}>
              <h2>{category.label}</h2>
              <div>
                <h3>What it looks like</h3>
                <p>{category.looksLike}</p>
              </div>
              <div>
                <h3>Why it matters for an investor</h3>
                <p>{category.whyItMatters}</p>
              </div>
              <div>
                <h3>A real signal vs. a vague one</h3>
                <p>{category.signal}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="resultsSection" style={{paddingTop: 0}}>
        <p className="resultNote" style={{maxWidth: 900}}>
          This page explains sustainable-investing concepts in general terms. It is educational content, not
          investment advice, and doesn&apos;t evaluate any specific security. For how Green Canopy actually scores
          and tags companies, see the <Link href="/methodology" style={{fontWeight: 800}}>methodology page</Link>.
        </p>
      </section>
    </main>
  );
}
