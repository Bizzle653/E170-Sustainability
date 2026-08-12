"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Portfolio = {
  investor_profile?: {
    profile_name?: string;
    profile_description?: string;
    sustainability_priority_weights?: Record<string, number>;
  };
  sustainability_alignment_score?: number;
  annualized_volatility?: number;
  maximum_drawdown?: number;
  total_investment_amount?: number;
  allocations?: Array<{
    ticker: string;
    name: string;
    weight: number;
    matched_priorities?: string[];
  }>;
};

type ProfileContext = {
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

type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

const EXAMPLES = [
  "What should I do if markets fall sharply?",
  "Why was this portfolio selected for me?",
  "How can I reduce concentration risk?",
  "What should I change if I want more income?",
];

const PRIORITY_LABELS: Record<string, string> = {
  climate: "climate",
  renewable_energy: "clean energy",
  fair_labor: "fair labor",
  human_rights: "human rights",
  biodiversity: "biodiversity",
  clean_water: "clean water",
  sustainable_agriculture: "sustainable agriculture",
  circular_economy: "circularity",
  governance: "governance",
};

function readStoredContext() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem("greenCanopyDecisionContext");
    return raw ? (JSON.parse(raw) as ProfileContext) : null;
  } catch {
    return null;
  }
}

function readStoredPortfolio() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem("greenCanopyPortfolio");
    return raw ? (JSON.parse(raw) as Portfolio) : null;
  } catch {
    return null;
  }
}

function formatCurrency(value?: number) {
  if (typeof value !== "number") return "$0";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function buildReply(input: string, context: ProfileContext | null, portfolio: Portfolio | null) {
  const lower = input.toLowerCase();
  const topPriorities = (context?.priorities ?? []).map((item) => PRIORITY_LABELS[item] ?? item).slice(0, 3);
  const horizon = context?.horizon === "10_plus_years" ? "10+ years" : context?.horizon === "3_to_10_years" ? "3-10 years" : "under 3 years";
  const philosophy = context?.philosophy === "avoid_harm" ? "avoid harm" : context?.philosophy === "fund_solutions" ? "fund solutions" : "combine both";
  const riskProfile = context?.risk === "move_to_safety" ? "a defensive posture" : context?.risk === "invest_more" ? "an opportunistic stance" : "a steady, long-term stance";
  const largestHolding = portfolio?.allocations?.[0];
  const concentration = largestHolding ? largestHolding.weight : 0;
  const alignmentScore = portfolio?.sustainability_alignment_score ?? 0;

  if (/risk|volatile|drawdown|fall|drop|market|panic/i.test(lower)) {
    return `Your profile points to ${riskProfile}. I would keep the plan steady unless you need the money before ${horizon}. If you are nervous about a sharp drop, focus on staying diversified, keeping the largest holding below ${Math.max(20, Math.round((context?.max_concentration ?? 0.2) * 100))}% of the portfolio, and reviewing whether your emergency needs changed. ${alignmentScore >= 70 ? "Your current alignment is strong, so the main adjustment is risk-control rather than a full reset." : "Because the portfolio is still relatively new, it is reasonable to trim the most concentrated position before making any larger changes."}`;
  }

  if (/income|yield|dividend|cash/i.test(lower)) {
    return `If you want more income, I would look first at reducing concentration in the highest-growth holdings and introducing more balanced holdings with steadier cash flows. Since your goal is ${context?.goal?.replaceAll("_", " ") || "long-term growth"}, the best fit is usually a modest shift rather than a dramatic change. Keep your top priorities of ${topPriorities.join(", ") || "your selected themes"} in place while making the portfolio less dependent on one position.`;
  }

  if (/why|selected|choose|explain|reason/i.test(lower)) {
    return `This portfolio was shaped around your values, your timeline, and your comfort with market swings. The strongest signals are ${topPriorities.join(", ") || "your selected priorities"}, a ${philosophy} preference, and a ${horizon} horizon. The assistant uses those signals to prefer holdings that fit your values without ignoring diversification and downside risk.`;
  }

  if (/concentr|divers|spread|balance/i.test(lower)) {
    return `Concentration risk is the main thing I would watch. The largest holding is currently about ${concentration.toFixed(1)}% of the portfolio, so a small trim or a modest rebalance could help. A simple rule is to keep the biggest position under ${Math.max(20, Math.round((context?.max_concentration ?? 0.2) * 100))}% and spread exposure across sectors that still fit your priorities.`;
  }

  if (/sell|buy|change|rebalance|adjust/i.test(lower)) {
    return `I would make changes gradually. Start by asking whether you need the money in the next ${horizon}. If the answer is yes, the safer move is to reduce volatility and keep liquidity. If the answer is no, a modest rebalance can preserve your values while improving resilience.`;
  }

  return `You are building around ${topPriorities.join(", ") || "your selected priorities"} with a ${philosophy} approach and a ${horizon} horizon. My guidance is to stay aligned with your values, keep diversification intact, and only make meaningful changes when your financial need, risk comfort, or market outlook changes. If you want, I can also help you compare a more defensive, income-oriented, or growth-oriented path.`;
}

export function DecisionAssistant() {
  const [context, setContext] = useState<ProfileContext | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const storedContext = readStoredContext();
      const storedPortfolio = readStoredPortfolio();
      setContext(storedContext);
      setPortfolio(storedPortfolio);
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content: storedContext
            ? `I’m your decision coach. I can help you interpret your profile and next steps for your portfolio. You selected ${storedContext.priorities.slice(0, 3).map((item) => PRIORITY_LABELS[item] ?? item).join(", ") || "your priorities"} and your horizon is ${storedContext.horizon === "10_plus_years" ? "10+ years" : storedContext.horizon === "3_to_10_years" ? "3-10 years" : "under 3 years"}.`
            : "I’m your decision coach. I can help you interpret your portfolio and next steps. Create or review a portfolio and I’ll tailor the guidance.",
        },
      ]);
      setReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const summary = useMemo(() => {
    if (!context) return "No profile saved yet";
    return `${context.priorities.slice(0, 3).map((item) => PRIORITY_LABELS[item] ?? item).join(", ") || "your priorities"} · ${context.goal.replaceAll("_", " ")} · ${context.horizon === "10_plus_years" ? "10+ years" : context.horizon === "3_to_10_years" ? "3-10 years" : "under 3 years"}`;
  }, [context]);

  function submitQuestion(event: FormEvent) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMessage: Message = { id: `${Date.now()}-user`, role: "user", content: trimmed };
    const assistantReply = buildReply(trimmed, context, portfolio);
    const assistantMessage: Message = { id: `${Date.now()}-assistant`, role: "assistant", content: assistantReply };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
  }

  return (
    <section className="assistantPanel">
      <div className="assistantIntro">
        <div>
          <span className="eyebrow">Decision support</span>
          <h2>Talk with your client advisor.</h2>
          <p>Use this guide to turn your portfolio results into clear next steps. The responses are tailored to the profile you already built and the portfolio you generated.</p>
        </div>
        <div className="assistantSnapshot">
          <strong>Current focus</strong>
          <span>{summary}</span>
          <small>{portfolio ? `${formatCurrency(portfolio.total_investment_amount)} invested · ${portfolio.allocations?.length ?? 0} holdings` : "Create a portfolio to unlock richer guidance"}</small>
        </div>
      </div>

      <div className="assistantPromptRow">
        {EXAMPLES.map((example) => (
          <button type="button" key={example} onClick={() => setInput(example)}>{example}</button>
        ))}
      </div>

      <div className="chatSurface" aria-live="polite">
        {messages.map((message) => (
          <div key={message.id} className={`chatBubble ${message.role}`}>
            <strong>{message.role === "assistant" ? "Advisor" : "You"}</strong>
            <p>{message.content}</p>
          </div>
        ))}
      </div>

      <form className="assistantComposer" onSubmit={submitQuestion}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={ready ? "Ask about risk, diversification, income, or trade-offs" : "Loading your guidance…"}
          disabled={!ready}
        />
        <button type="submit" className="button" disabled={!ready}>Send</button>
      </form>
    </section>
  );
}
