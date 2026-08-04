"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
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

const SUGGESTIONS = [
  "How does Green Canopy build a sustainable portfolio?",
  "What does the alignment score mean?",
  "Help me understand diversification and risk",
  "Tell me about the sustainability categories you track",
];

// ---------------------------------------------------------------------------
// Full-page Chat — reuses .chatBubble / .chatSurface / .assistantComposer /
// .assistantPromptRow from globals.css
// ---------------------------------------------------------------------------

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm your Sustainability AI Copilot. I can explain how your portfolio is built, what the alignment and risk scores mean, and answer questions about the investment universe and methodology. How can I help you today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

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

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    sendMessage(input);
  }

  // -------------------------------------------------------------------
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        background: "var(--cream)",
        minHeight: 0,
      }}
    >
      {/* Messages area — reuses .chatSurface (unbounded height) */}
      <div className="chatSurface" style={{ flex: 1, maxHeight: "none", padding: "24px" }}>
        {messages.length < 2 && (
          <div className="assistantPromptRow">
            {SUGGESTIONS.map((s) => (
              <button type="button" key={s} onClick={() => sendMessage(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chatBubble ${msg.role}`}
            style={{ maxWidth: "72%" }}
          >
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
                      ol: ({ children }) => <ol style={{ paddingLeft: 18, margin: 0 }}>{children}</ol>,
                      code: ({ children }) => (
                        <code style={{ background: "var(--soft)", padding: "1px 4px", borderRadius: 4, fontSize: 11 }}>
                          {children}
                        </code>
                      ),
                      table: ({ children }) => (
                        <div style={{ overflowX: "auto", margin: "8px 0" }}>
                          <table style={{ borderCollapse: "collapse", fontSize: 11, width: "100%" }}>
                            {children}
                          </table>
                        </div>
                      ),
                      th: ({ children }) => (
                        <th style={{ border: "1px solid var(--line)", padding: "4px 8px", background: "var(--soft)", textAlign: "left" }}>
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td style={{ border: "1px solid var(--line)", padding: "4px 8px" }}>
                          {children}
                        </td>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote style={{ borderLeft: "2px solid var(--leaf)", paddingLeft: 12, color: "var(--muted)", fontStyle: "italic", margin: "8px 0" }}>
                          {children}
                        </blockquote>
                      ),
                      h1: ({ children }) => <h3 style={{ fontSize: 15, fontWeight: 800, margin: "12px 0 4px" }}>{children}</h3>,
                      h2: ({ children }) => <h4 style={{ fontSize: 13, fontWeight: 800, margin: "10px 0 4px" }}>{children}</h4>,
                      h3: ({ children }) => <h5 style={{ fontSize: 12, fontWeight: 800, margin: "8px 0 2px" }}>{children}</h5>,
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
          </div>
        ))}

        {isLoading && (
          <div className="chatBubble" style={{ maxWidth: "72%" }}>
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
          placeholder={isLoading ? "Waiting for a response..." : "Ask AI Assistant anything..."}
          disabled={isLoading}
        />
        <button type="submit" className="button" disabled={!input.trim() || isLoading}>
          Send
        </button>
      </form>
    </div>
  );
}
