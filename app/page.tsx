"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { HeroTicker } from "@/components/MarketPulse";
import { getSupabaseBrowserClient } from "@/lib/supabase";

type Answers = {
  priorities: string[];
  goal: string;
  horizon: string;
  risk: string;
  decline_reaction: string;
  philosophy: string;
  tradeoff: string;
  exclusions: string[];
  max_concentration: number;
  amount: number;
};

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
const steps = [
  ["Your values", "What matters most to you?", "Choose up to three priorities. Order matters: your first choice receives the strongest weight."],
  ["Your philosophy", "How should your money create change?", "Tell us whether you prefer avoiding harmful companies outright, funding solutions directly, or a combination of both."],
  ["Your boundaries", "What should your portfolio avoid?", "Explicit exclusions are treated as constraints, not suggestions."],
  ["Your objective", "What is this money for?", "Your goal helps balance long-term growth, stability, and income."],
  ["Your timeline", "When might you need this money?", "A longer runway can support more exposure to market movement."],
  ["Your comfort level", "How would you handle a difficult year?", "Your response to a hypothetical 20% decline shapes the risk penalty."],
  ["Starting amount", "How much would you like to invest?", "This illustrative amount determines the dollar allocation in your simulated portfolio."],
];
const loadingStages = [
  "Building your investor profile",
  "Retrieving company data",
  "Checking sustainability alignment",
  "Evaluating financial risk",
  "Optimizing your portfolio",
  "Preparing your results",
];

export default function Home() {
  const router = useRouter();
  const {user} = useAuth();
  const [builderOpen, setBuilderOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState<Answers>({
    priorities: ["climate", "biodiversity"],
    goal: "long_term_growth",
    horizon: "10_plus_years",
    risk: "stay_invested",
    decline_reaction: "hold",
    philosophy: "combination",
    tradeoff: "small",
    exclusions: ["fossil_fuels"],
    max_concentration: 0.2,
    amount: 10000,
  });

  function toggleList(field: "priorities" | "exclusions", value: string, limit = 99) {
    setAnswers((current) => {
      const values = current[field];
      return {
        ...current,
        [field]: values.includes(value) ? values.filter((item) => item !== value) : values.length < limit ? [...values, value] : values,
      };
    });
  }

  async function generate() {
    setLoading(true);
    setError("");
    setLoadingStage(0);
    const timer = window.setInterval(() => setLoadingStage((value) => Math.min(value + 1, loadingStages.length - 1)), 1500);
    try {
      const response = await fetch(`${API_URL}/api/portfolio/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          investment_amount: answers.amount,
          number_of_holdings: 8,
          answers: {
            priorities: answers.priorities,
            goal: answers.goal,
            horizon: answers.horizon,
            risk: answers.risk,
            decline_reaction: answers.decline_reaction,
            philosophy: answers.philosophy,
            tradeoff: answers.tradeoff,
            exclusions: answers.exclusions,
            max_concentration: answers.max_concentration,
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Portfolio generation failed");
      localStorage.setItem("greenCanopyPortfolio", JSON.stringify(payload));
      localStorage.removeItem("greenCanopyQuotes");
      const supabase = getSupabaseBrowserClient();
      if (supabase && user) {
        await supabase.from("portfolios").upsert({
          user_id: user.id,
          data: payload,
          updated_at: new Date().toISOString(),
        });
      }
      router.push("/results");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not build the portfolio.");
      setLoading(false);
    } finally {
      window.clearInterval(timer);
    }
  }

  return (
    <main>
      <nav className="nav">
        <a className="brand" href="#"><span className="brandMark">⌁</span><span>Green Canopy</span></a>
        <div className="navLinks"><a href="/learn">Learn</a><a href="/methodology">Methodology</a></div>
        <div className="navActions"><a className="backButton navButton" href="/review">Review my holdings</a>{user ? <a className="backButton navButton" href="/portfolio">My dashboard</a> : <a className="backButton navButton" href="/login">Sign in</a>}<button className="button buttonSmall" onClick={() => setBuilderOpen(true)}>Build your portfolio</button></div>
      </nav>

      <section className="hero">
        <div className="heroShade" />
        <div className="heroContent">
          <span className="eyebrow">Sustainable investing, made personal</span>
          <h1>Invest with purpose.<br />Grow a better future.</h1>
          <p>Build an educational portfolio simulation around the causes you care about—without losing sight of diversification, historical risk, and your financial goals.</p>
          <div className="heroActions"><button className="button" onClick={() => setBuilderOpen(true)}>Get started <span>→</span></button><a className="textLink" href="#how">See how it works</a></div>
          <div className="trustLine"><span>✓ No brokerage connection</span><span>✓ Transparent scoring</span><span>✓ Educational simulation</span></div>
          <HeroTicker />
        </div>
      </section>

      <section className="section" id="how">
        <div className="sectionIntro centered"><span className="eyebrow">A clearer path</span><h2>From your values to a portfolio you understand.</h2><p>We turn your answers into a real portfolio, calculated from live market data. Every result explains exactly what it knows, and what it doesn&apos;t.</p></div>
        <div className="steps">
          {[
            ["01", "Tell us what matters", "Prioritize climate, people, nature, water, circularity, and governance."],
            ["02", "Set your financial fit", "Add your objective, timeline, risk response, exclusions, and investment amount."],
            ["03", "Review every choice", "See real tickers, allocation math, historical metrics, confidence, and limitations."],
          ].map(([number, title, copy]) => <article className="stepCard" key={number}><span className="stepNumber">{number}</span><span className="stepIcon">{number === "01" ? "◎" : number === "02" ? "♧" : "↗"}</span><h3>{title}</h3><p>{copy}</p></article>)}
        </div>
      </section>

      <section className="section darkSection" id="approach">
        <div className="approachGrid">
          <div><span className="eyebrow lightEyebrow">A more personal approach</span><h2>A broad universe, screened for your priorities.</h2><p>The MVP begins with public-company coverage drawn from the Fortune 1000 scope and 100 of the largest U.S.-listed ETFs. It retrieves only the bounded candidate set needed for each simulation.</p><div className="pillRow">{["Climate", "Fair labor", "Biodiversity", "Clean water", "Renewables", "Circularity"].map((item) => <span key={item}>{item}</span>)}</div></div>
          <div className="analysisPanel"><span className="panelKicker">What we analyze</span>{[
            ["Values alignment", "Your priorities and exclusions"],
            ["Classification tags", "Climate, labor, water, and more — transparently scored"],
            ["Financial history", "Return, volatility, and drawdown"],
            ["Diversification", "Correlation and concentration"],
          ].map(([title, copy]) => <div className="analysisItem" key={title}><i>✓</i><div><strong>{title}</strong><small>{copy}</small></div></div>)}</div>
        </div>
      </section>

      <section className="section impactSection" id="impact"><div className="impactCard"><span className="eyebrow">Clear by design</span><h2>Every score explains itself.</h2><p>Each holding shows exactly which of your priorities it matches, a one-sentence description of what the company actually does, and the full reasoning behind its score—never a black-box number.</p><button className="button lightButton" onClick={() => setBuilderOpen(true)}>Create my profile</button></div></section>
      <footer><div className="brand"><span className="brandMark">⌁</span><span>Green Canopy</span></div><span>Educational simulation · Historical performance is not a guarantee · Not investment advice</span></footer>

      {builderOpen && <div className="modalBackdrop" role="dialog" aria-modal="true" aria-label="Build your Green Canopy portfolio">
        <div className="builder">
          <aside className="builderAside">
            <button className="closeButton" onClick={() => !loading && setBuilderOpen(false)} aria-label="Close portfolio builder">×</button>
            <div className="brand inverse"><span className="brandMark lightMark">⌁</span><span>Green Canopy</span></div>
            <div className="progressTrack"><span style={{ width: `${loading ? 100 : ((step + 1) / steps.length) * 100}%` }} /></div>
            <small>{loading ? "Analyzing your choices" : `Step ${step + 1} of ${steps.length}`}</small>
            <h2>Your values become the strategy.</h2><p>There are no right answers. Choose what feels true to you.</p>
            <div className="asideTags">{answers.priorities.map((key) => <span key={key}>{priorities.find((item) => item[0] === key)?.[1]}</span>)}</div>
          </aside>
          <section className="builderMain">
            {loading ? <div className="loadingState"><span className="loadingRing" /><span className="eyebrow">Building with care</span><h2>{loadingStages[loadingStage]}</h2><p>We’re retrieving a bounded candidate set and will clearly flag missing provider data.</p><div className="stageList">{loadingStages.map((stage, index) => <span className={index <= loadingStage ? "active" : ""} key={stage}>{index < loadingStage ? "✓" : index === loadingStage ? "•" : "○"} {stage}</span>)}</div></div> : <>
              <div><span className="eyebrow">{steps[step][0]}</span><h2>{steps[step][1]}</h2><p className="builderCopy">{steps[step][2]}</p></div>
              {step === 0 && <div className="choiceGrid">{priorities.map(([key, title, copy]) => <button className={`choiceCard ${answers.priorities.includes(key) ? "selected" : ""}`} onClick={() => toggleList("priorities", key, 3)} key={key}><span>{answers.priorities.includes(key) ? "✓" : "+"}</span><strong>{title}</strong><small>{copy}</small></button>)}</div>}
              {step === 1 && <OptionList value={answers.philosophy} options={[["avoid_harm","Avoid companies causing harm"],["fund_solutions","Fund direct solutions"],["combination","Combine these approaches"]]} onChange={(philosophy) => setAnswers({...answers, philosophy})} />}
              {step === 2 && <div className="choiceGrid">{exclusions.map(([key, title]) => <button className={`choiceCard compact ${answers.exclusions.includes(key) ? "selected" : ""}`} onClick={() => toggleList("exclusions", key)} key={key}><span>{answers.exclusions.includes(key) ? "✓" : "+"}</span><strong>{title}</strong><small>Exclude from consideration</small></button>)}</div>}
              {step === 3 && <OptionList value={answers.goal} options={[["long_term_growth","Long-term growth"],["growth_and_stability","Growth and stability"],["income_and_preservation","Income and preservation"]]} onChange={(goal) => setAnswers({...answers, goal})} />}
              {step === 4 && <OptionList value={answers.horizon} options={[["under_3_years","Under 3 years"],["3_to_10_years","3–10 years"],["10_plus_years","10+ years"]]} onChange={(horizon) => setAnswers({...answers, horizon})} />}
              {step === 5 && <><OptionList value={answers.risk} options={[["move_to_safety","Reduce risk after a decline"],["stay_invested","Stay invested"],["invest_more","Invest more at lower prices"]]} onChange={(risk) => setAnswers({...answers, risk, decline_reaction: risk === "move_to_safety" ? "sell" : risk === "invest_more" ? "buy_more" : "hold"})} /><label className="selectLabel">Sustainability trade-off<select value={answers.tradeoff} onChange={(event) => setAnswers({...answers, tradeoff: event.target.value})}><option value="none">No expected-return trade-off</option><option value="small">Small trade-off</option><option value="moderate">Moderate trade-off</option><option value="strong">Strong trade-off</option></select></label></>}
              {step === 6 && <div className="amountCard"><label htmlFor="amount">Investment amount</label><div><span>$</span><input id="amount" type="number" min="500" max="1000000" step="500" value={answers.amount} onChange={(event) => setAnswers({...answers, amount: Number(event.target.value)})} /></div><input className="range" type="range" min="500" max="100000" step="500" value={Math.min(100000, answers.amount)} onChange={(event) => setAnswers({...answers, amount: Number(event.target.value)})} /><small>$500 minimum <span>$1,000,000 maximum</span></small></div>}
              {error && <p className="errorMessage" role="alert">{error}</p>}
              <div className="builderActions"><button className="backButton" disabled={step === 0} onClick={() => setStep((value) => value - 1)}>Back</button><button className="button" disabled={(step === 0 && answers.priorities.length === 0) || answers.amount < 500} onClick={() => step === steps.length - 1 ? generate() : setStep((value) => value + 1)}>{step === steps.length - 1 ? "Create my portfolio" : "Continue"} <span>→</span></button></div>
            </>}
          </section>
        </div>
      </div>}
    </main>
  );
}

function OptionList({value, options, onChange}: {value: string; options: string[][]; onChange: (value: string) => void}) {
  return <div className="optionList">{options.map(([key, label]) => <button className={value === key ? "selected" : ""} onClick={() => onChange(key)} key={key}><span className="radio">{value === key && <i />}</span><strong>{label}</strong></button>)}</div>;
}
