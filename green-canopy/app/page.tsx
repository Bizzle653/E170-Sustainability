"use client";

import { useMemo, useState } from "react";

type Answers = {
  priorities: string[];
  goal: string;
  horizon: string;
  risk: string;
  amount: number;
};

const priorityOptions = [
  ["Climate", "Lower carbon emissions"],
  ["Clean energy", "Renewables and storage"],
  ["Fair work", "Labor and human rights"],
  ["Nature", "Biodiversity protection"],
  ["Water", "Access and efficiency"],
  ["Circularity", "Waste and materials"],
];

const steps = [
  { eyebrow: "Your values", title: "What matters most to you?", copy: "Choose up to three themes. We’ll use them as the strongest sustainability weights in your portfolio." },
  { eyebrow: "Your objective", title: "What is this money for?", copy: "Your goal helps us balance long-term growth, stability, and income." },
  { eyebrow: "Your timeline", title: "When might you need this money?", copy: "A longer runway can support more exposure to market movement." },
  { eyebrow: "Your comfort level", title: "How do you feel about market swings?", copy: "Choose the answer that best reflects how you would react during a difficult year." },
  { eyebrow: "Starting amount", title: "How much would you like to invest?", copy: "This illustrative amount determines the dollar allocation in your sample portfolio." },
];

export default function Home() {
  const [builderOpen, setBuilderOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [complete, setComplete] = useState(false);
  const [answers, setAnswers] = useState<Answers>({
    priorities: ["Climate", "Nature"],
    goal: "Long-term growth",
    horizon: "10+ years",
    risk: "Stay invested",
    amount: 10000,
  });

  const riskLabel = answers.risk === "Invest more" ? "Growth" : answers.risk === "Move to safety" ? "Cautious" : "Balanced";
  const holdings = useMemo(() => {
    const themes = answers.priorities.length ? answers.priorities : ["Climate"];
    const thematic = riskLabel === "Growth" ? 58 : riskLabel === "Cautious" ? 38 : 48;
    return [
      { name: `${themes[0]} Leaders`, description: "High-alignment global companies", percent: Math.round(thematic * 0.58) },
      { name: `${themes[1] ?? "Clean energy"} Solutions`, description: "Companies building measurable solutions", percent: Math.round(thematic * 0.42) },
      { name: "Sustainable Market Core", description: "Broad screened diversification", percent: riskLabel === "Growth" ? 32 : 37 },
      { name: "Green Bond Reserve", description: "Stability and climate-linked income", percent: riskLabel === "Growth" ? 10 : riskLabel === "Cautious" ? 25 : 15 },
    ];
  }, [answers.priorities, riskLabel]);

  function startBuilder() {
    setBuilderOpen(true);
    setComplete(false);
    setStep(0);
  }

  function next() {
    if (step === steps.length - 1) setComplete(true);
    else setStep((value) => value + 1);
  }

  function togglePriority(value: string) {
    setAnswers((current) => {
      const selected = current.priorities.includes(value);
      const priorities = selected
        ? current.priorities.filter((item) => item !== value)
        : current.priorities.length < 3
          ? [...current.priorities, value]
          : current.priorities;
      return { ...current, priorities };
    });
  }

  return (
    <main>
      <header className="nav">
        <a className="brand" href="#top" aria-label="Green Canopy home">
          <span className="brandMark">⌁</span>
          <span>Green Canopy</span>
        </a>
        <nav className="navLinks" aria-label="Primary navigation">
          <a href="#how">How it works</a>
          <a href="#approach">Our approach</a>
          <a href="#impact">Impact</a>
        </nav>
        <button className="button buttonSmall" onClick={startBuilder}>Get started</button>
      </header>

      <section className="hero" id="top">
        <div className="heroShade" />
        <div className="heroContent">
          <span className="eyebrow">Personalized sustainable investing</span>
          <h1>Invest with purpose.<br />Grow a better future.</h1>
          <p>Build a diversified portfolio that reflects your values, financial goals, and appetite for risk—without reducing sustainability to a single score.</p>
          <div className="heroActions">
            <button className="button" onClick={startBuilder}>Build your portfolio <span>→</span></button>
            <a className="textLink" href="#how">See how it works</a>
          </div>
          <div className="trustLine">
            <span>✓ Personalized</span><span>✓ Sustainability-led</span><span>✓ Risk-aware</span>
          </div>
        </div>
      </section>

      <section className="section" id="how">
        <div className="sectionIntro centered">
          <span className="eyebrow">How it works</span>
          <h2>A portfolio designed around you.</h2>
          <p>Thoughtful questions become a practical, transparent investment strategy.</p>
        </div>
        <div className="steps">
          {[
            ["01", "Tell us what matters", "Share your values, goals, time horizon, and comfort with risk."],
            ["02", "We build your profile", "Your answers become clear sustainability and financial preferences."],
            ["03", "Grow with impact", "See an illustrative allocation and the reasoning behind every choice."],
          ].map(([number, title, copy]) => (
            <article className="stepCard" key={number}>
              <span className="stepNumber">{number}</span>
              <span className="stepIcon">{number === "01" ? "◎" : number === "02" ? "♧" : "↗"}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section darkSection" id="approach">
        <div className="approachGrid">
          <div>
            <span className="eyebrow lightEyebrow">A more personal approach</span>
            <h2>Sustainability means something different to everyone.</h2>
            <p>Green Canopy asks where you want to avoid harm, where you want to fund solutions, and how much flexibility you’re comfortable giving up for closer alignment.</p>
            <div className="pillRow">
              {["Climate", "Fair labor", "Biodiversity", "Clean water", "Renewables", "Circularity"].map((item) => <span key={item}>{item}</span>)}
            </div>
          </div>
          <div className="analysisPanel">
            <span className="panelKicker">What we analyze</span>
            {[
              ["Environmental impact", "Emissions, resources, and policy"],
              ["Social responsibility", "Labor, community, and rights"],
              ["Governance quality", "Leadership and accountability"],
              ["Financial resilience", "Growth, stability, and risk"],
            ].map(([title, copy]) => <div className="analysisItem" key={title}><i>✓</i><div><strong>{title}</strong><small>{copy}</small></div></div>)}
          </div>
        </div>
      </section>

      <section className="section impactSection" id="impact">
        <div className="impactCard">
          <span className="eyebrow">Clear by design</span>
          <h2>Know why every investment belongs.</h2>
          <p>Each illustrative allocation explains how it supports your priorities, contributes to diversification, and fits your risk profile.</p>
          <button className="button lightButton" onClick={startBuilder}>Create my profile</button>
        </div>
      </section>

      <footer>
        <div className="brand"><span className="brandMark">⌁</span><span>Green Canopy</span></div>
        <span>Educational prototype · Illustrative portfolios only · Not investment advice</span>
      </footer>

      {builderOpen && (
        <div className="modalBackdrop" role="dialog" aria-modal="true" aria-label="Build your Green Canopy portfolio">
          <div className="builder">
            <aside className="builderAside">
              <button className="closeButton" onClick={() => setBuilderOpen(false)} aria-label="Close portfolio builder">×</button>
              <div className="brand inverse"><span className="brandMark lightMark">⌁</span><span>Green Canopy</span></div>
              <div className="progressTrack"><span style={{ width: `${complete ? 100 : ((step + 1) / steps.length) * 100}%` }} /></div>
              <small>{complete ? "Profile complete" : `Step ${step + 1} of ${steps.length}`}</small>
              <h2>Your values become the strategy.</h2>
              <p>There are no right answers. Choose what feels true to you.</p>
              <div className="asideTags">{answers.priorities.map((item) => <span key={item}>{item}</span>)}</div>
            </aside>

            <section className="builderMain">
              {!complete ? (
                <>
                  <div>
                    <span className="eyebrow">{steps[step].eyebrow}</span>
                    <h2>{steps[step].title}</h2>
                    <p className="builderCopy">{steps[step].copy}</p>
                  </div>

                  {step === 0 && <div className="choiceGrid">{priorityOptions.map(([title, copy]) => {
                    const selected = answers.priorities.includes(title);
                    return <button className={`choiceCard ${selected ? "selected" : ""}`} onClick={() => togglePriority(title)} key={title}><span>{selected ? "✓" : "+"}</span><strong>{title}</strong><small>{copy}</small></button>;
                  })}</div>}

                  {step === 1 && <OptionList value={answers.goal} options={["Long-term growth", "Growth and stability", "Income and preservation"]} onChange={(goal) => setAnswers({ ...answers, goal })} />}
                  {step === 2 && <OptionList value={answers.horizon} options={["Under 3 years", "3–10 years", "10+ years"]} onChange={(horizon) => setAnswers({ ...answers, horizon })} />}
                  {step === 3 && <OptionList value={answers.risk} options={["Move to safety", "Stay invested", "Invest more"]} onChange={(risk) => setAnswers({ ...answers, risk })} />}
                  {step === 4 && <div className="amountCard"><label htmlFor="amount">Investment amount</label><div><span>$</span><input id="amount" type="number" min="500" max="1000000" step="500" value={answers.amount} onChange={(event) => setAnswers({ ...answers, amount: Number(event.target.value) })} /></div><input className="range" type="range" min="500" max="100000" step="500" value={Math.min(100000, answers.amount)} onChange={(event) => setAnswers({ ...answers, amount: Number(event.target.value) })} /><small>$500 minimum <span>$1,000,000 maximum</span></small></div>}

                  <div className="builderActions">
                    <button className="backButton" disabled={step === 0} onClick={() => setStep((value) => value - 1)}>Back</button>
                    <button className="button" disabled={step === 0 && answers.priorities.length === 0} onClick={next}>{step === steps.length - 1 ? "Create my portfolio" : "Continue"} <span>→</span></button>
                  </div>
                </>
              ) : (
                <div className="results">
                  <span className="eyebrow">Your Green Canopy profile</span>
                  <h2>The Purpose Builder</h2>
                  <p className="builderCopy">A {riskLabel.toLowerCase()} investor focused on {answers.priorities.join(" and ").toLowerCase()}, with a {answers.horizon.toLowerCase()} time horizon.</p>
                  <div className="resultStats"><div><small>Investment</small><strong>${answers.amount.toLocaleString()}</strong></div><div><small>Risk profile</small><strong>{riskLabel}</strong></div><div><small>Alignment</small><strong>88/100</strong></div></div>
                  <div className="holdings">{holdings.map((holding) => <div key={holding.name}><span className="holdingMark">{holding.name.slice(0, 2).toUpperCase()}</span><span><strong>{holding.name}</strong><small>{holding.description}</small></span><b>{holding.percent}%</b><em>${Math.round(answers.amount * holding.percent / 100).toLocaleString()}</em></div>)}</div>
                  <p className="resultNote"><strong>Why this mix:</strong> Dedicated theme exposure reflects your priorities, while the sustainable core and bond reserve help keep the portfolio diversified.</p>
                  <div className="builderActions"><button className="backButton" onClick={() => { setComplete(false); setStep(0); }}>Retake</button><button className="button" onClick={() => setBuilderOpen(false)}>Done</button></div>
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </main>
  );
}

function OptionList({ value, options, onChange }: { value: string; options: string[]; onChange: (value: string) => void }) {
  return <div className="optionList">{options.map((option) => <button className={value === option ? "selected" : ""} onClick={() => onChange(option)} key={option}><span className="radio">{value === option && <i />}</span><strong>{option}</strong></button>)}</div>;
}
