"use client";

import Link from "next/link";
import { ChatInterface } from "@/components/ChatInterface";

export default function ChatPage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--cream)", display: "flex", flexDirection: "column" }}>
      {/* Header — mirrors .resultsNav */}
      <header
        style={{
          height: 76,
          padding: "0 max(5vw, 24px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--forest)",
          color: "#fff",
        }}
      >
        <div className="brand" style={{ fontSize: 18 }}>
          <span className="brandMark" style={{ width: 34, height: 34, fontSize: 20 }}>
            ✦
          </span>
          <div>
            <span>Sustainability AI Copilot</span>
            <small
              style={{
                display: "block",
                fontSize: 9,
                color: "var(--lime)",
                opacity: 0.7,
                fontWeight: 400,
                letterSpacing: 0,
              }}
            >
              Powered by DeepSeek
            </small>
          </div>
        </div>

        <div className="navActions">
          <Link className="backButton navButton" href="/methodology" style={{ background: "transparent", color: "#fff", borderColor: "rgba(255,255,255,.3)" }}>
            Methodology
          </Link>
          <Link className="button buttonSmall" href="/" style={{ background: "var(--lime)", color: "var(--forest)", boxShadow: "none" }}>
            ← Home
          </Link>
        </div>
      </header>

      {/* Chat area — flex fills remaining space */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", maxWidth: 880, width: "100%", margin: "0 auto", minHeight: 0 }}>
        <ChatInterface />
      </main>

      {/* Footer disclaimer */}
      <footer
        style={{
          textAlign: "center",
          padding: "12px max(5vw, 24px)",
          borderTop: "1px solid var(--line)",
          background: "#fff",
          fontSize: 10,
          color: "var(--muted)",
          lineHeight: 1.6,
        }}
      >
        Green Canopy does not provide financial advice. The AI assistant
        explains data already computed by the deterministic portfolio
        optimiser — it does not invent ESG scores, pick investments, or
        predict returns.{" "}
        <Link href="/methodology" style={{ textDecoration: "underline", fontWeight: 800 }}>
          Learn more about our methodology
        </Link>
        .
      </footer>
    </div>
  );
}