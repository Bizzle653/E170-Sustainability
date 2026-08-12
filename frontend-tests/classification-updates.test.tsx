import {fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import ClassificationUpdatesPage from "@/app/classification-updates/page";

const update = (id: string, ticker: string) => ({
  id,
  ticker,
  name: `${ticker} Company`,
  asset_type: "stock",
  published_at: "2026-08-12T00:00:00Z",
  model: "deepseek-chat",
  added_tags: ["climate"],
  removed_tags: [],
  added_exclusions: [],
  removed_exclusions: [],
  summary: "Evidence-backed change.",
  confidence: 0.9,
  evidence: [],
  greenwashing_flags: [],
  portfolio_impact: "Scores may change; allocations do not.",
});

describe("classification announcement pagination", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads older announcements instead of hiding history after 100 records", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ok: true, json: async () => ({updates: [update("1", "MSFT")], total: 2, next_offset: 1})})
      .mockResolvedValueOnce({ok: true, json: async () => ({updates: [update("2", "AAPL")], total: 2, next_offset: null})});
    vi.stubGlobal("fetch", fetchMock);

    render(<ClassificationUpdatesPage />);
    expect(await screen.findByText("MSFT Company")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", {name: /Load older announcements/}));
    expect(await screen.findByText("AAPL Company")).toBeInTheDocument();
    expect(screen.queryByRole("button", {name: /Load older announcements/})).not.toBeInTheDocument();
  });
});
