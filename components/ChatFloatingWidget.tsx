"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { apiUrl } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Message = {
  id: string;
  role: "assistant" | "error" | "user";
  content: string;
};

// ---------------------------------------------------------------------------
// Slide-over Chat Drawer — reuses existing .modalBackdrop / .chatBubble /
// .assistantComposer / .assistantPromptRow from globals.css
// ---------------------------------------------------------------------------

export function ChatFloatingWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm your Sustainability AI Copilot. Ask me about your portfolio, sustainability scores, risk, or methodology.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
      // Focus input shortly after the drawer animates in
      const timer = setTimeout(() => inputRef.current?.focus(), 200);
      return () => {
        document.body.style.overflow = "";
        clearTimeout(timer);
      };
    }
    document.body.style.overflow = "";
  }, [isOpen]);

  // -------------------------------------------------------------------
  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-user`, role: "user", content: trimmed },
      ]);
      setInput("");
      setIsLoading(true);

      try {
        const res = await fetch(apiUrl("/api/chat"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          { id: `${Date.now()}-assistant`, role: "assistant", content: data.reply || "" },
        ]);
      } catch (err: unknown) {
        const detail = err instanceof Error ? err.message : "Unknown error";
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-error`,
            role: "assistant",
            content: `Could not reach the assistant (${detail}). Please try again shortly.`,
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading],
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  // -------------------------------------------------------------------
  return (
    <>
      {/* FAB trigger — reuses .button + .buttonSmall pattern */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => {
            setInput("");
            setIsOpen(true);
          }}
          className="button buttonSmall fixed bottom-6 right-6 z-50"
          style={{ display: "inline-flex" }}
          aria-label="Open AI Assistant"
        >
          AI Copilot
        </button>
      )}

      {/* Scrim — reuses .modalBackdrop */}
      {isOpen && (
        <div
          className="modalBackdrop"
          style={{ placeItems: "stretch", padding: 0, zIndex: 90 }}
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Drawer panel — reuses .dashboardPanel as the card base */}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          height: "100%",
          width: "min(440px, calc(100vw - 16px))",
          zIndex: 91,
          display: "flex",
          flexDirection: "column",
          background: "var(--cream)",
          boxShadow: "0 0 0 1px var(--line), -16px 0 80px rgba(8,55,38,.16)",
          transition: "transform 280ms ease-out",
          transform: isOpen ? "translateX(0)" : "translateX(100%)",
        }}
      >
        {/* Header — mirrors .resultsNav height + .brand pattern */}
        <div
          style={{
            height: 76,
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--forest)",
            color: "#fff",
          }}
        >
          <div className="brand" style={{ fontSize: 16 }}>
            <span className="brandMark" style={{ width: 32, height: 32, fontSize: 18 }}>
              ✦
            </span>
            <span>AI Copilot</span>
          </div>
          <div className="navActions">
            <a href="/chat" className="navButton" style={{ borderColor: "rgba(255,255,255,.3)", color: "#fff" }}>
              Expand
            </a>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="navButton"
              style={{ borderColor: "rgba(255,255,255,.3)", color: "#fff" }}
              aria-label="Close drawer"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Messages — reuses .chatSurface + .chatBubble */}
        <div className="chatSurface" style={{ flex: 1, maxHeight: "none", padding: "24px 24px 0" }}>
          <div className="assistantPromptRow">
            {["How are alignment scores calculated?", "What does my risk score mean?", "How can I reduce concentration risk?"].map((s) => (
              <button type="button" key={s} onClick={() => sendMessage(s)}>{s}</button>
            ))}
          </div>

          {messages.map((msg) => (
            <div key={msg.id} className={`chatBubble ${msg.role}`} style={{ maxWidth: "92%" }}>
              {msg.role === "assistant" && (
                <>
                  <strong>AI Copilot</strong>
                  <div>
                    <ReactMarkdown
                      components={{
                        a: ({ href, children }) => (
                          <a href={href} target="_blank" rel="noopener noreferrer" className="textLink">
                            {children}
                          </a>
                        ),
                        ul: ({ children }) => <ul className="evidenceList">{children}</ul>,
                        code: ({ children }) => (
                          <code style={{ background: "var(--soft)", padding: "1px 4px", borderRadius: 4, fontSize: 11 }}>
                            {children}
                          </code>
                        ),
                        p: ({ children }) => <span>{children}</span>,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                </>
              )}
              {msg.role === "user" && (
                <>
                  <strong>You</strong>
                  <p>{msg.content}</p>
                </>
              )}
              {msg.role === "error" && (
                <>
                  <strong>AI Copilot</strong>
                  <p>{msg.content}</p>
                </>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="chatBubble" style={{ maxWidth: "92%" }}>
              <strong>AI Copilot</strong>
              <p style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 16,
                    height: 16,
                    borderRadius: "50%",
                    border: "2.5px solid var(--soft)",
                    borderTopColor: "var(--forest)",
                    animation: "spin .75s linear infinite",
                  }}
                />
                Thinking &hellip;
              </p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Composer — reuses .assistantComposer */}
        <form
          className="assistantComposer"
          style={{ padding: "16px 24px", margin: 0, background: "#fff", borderTop: "1px solid var(--line)" }}
          onSubmit={handleSubmit}
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isLoading ? "Waiting..." : "Ask AI Assistant anything..."}
            disabled={isLoading}
          />
          <button type="submit" className="button" disabled={!input.trim() || isLoading}>
            Send
          </button>
        </form>
      </div>
    </>
  );
}
