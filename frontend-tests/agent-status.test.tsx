import {render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import AgentStatusPage from "@/app/agent-status/page";

describe("Agent status page", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows verified coverage and retry health returned by the public API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        agent: "Green Canopy Sustainability Intelligence Agent",
        policy_version: "2026-08-12.1",
        prompt_version: "classification-v2-exact-citations",
        total_securities: 1055,
        verified_securities: 42,
        checked_securities: 45,
        pending_securities: 1013,
        coverage_percent: 4,
        retry_count: 1,
        retry_queue: [{ticker: "TEST", failure_count: 2, next_retry_at: "2026-08-12T12:00:00Z"}],
        last_run: {status: "partial", selected: 20, succeeded: 19, changed: 1, failed: 1},
      }),
    }));

    render(<AgentStatusPage />);

    expect(await screen.findByText("42 of 1055 securities verified")).toBeInTheDocument();
    expect(screen.getByText(/Latest autonomous run: partial/)).toBeInTheDocument();
    expect(screen.getByText(/TEST: attempt 2/)).toBeInTheDocument();
  });
});
