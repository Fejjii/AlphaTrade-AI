import { describe, expect, it } from "vitest";

import { failedSource, okSource } from "@/components/workflows/sourceResult";
import {
  importantAlerts,
  marketEvidenceLabel,
  portfolioEquity,
  portfolioWinRate,
  watcherTraderLabel,
} from "@/components/dashboard/trader-dashboard";
import { UNAVAILABLE } from "@/lib/format";
import type { PaperAlert, PaperPortfolioResponse } from "@/lib/api/types";

describe("trader dashboard view model", () => {
  it("maps watcher and market evidence into trader language", () => {
    expect(watcherTraderLabel("RUNNING")).toBe("Watching");
    expect(watcherTraderLabel("STOPPED")).toBe("Stopped");
    expect(watcherTraderLabel("DEGRADED")).toBe("Degraded");
    expect(watcherTraderLabel("STALE")).toBe("Stale");
    expect(watcherTraderLabel("BLOCKED")).toBe("Blocked");
    expect(watcherTraderLabel(null)).toBe("Unavailable");
    expect(marketEvidenceLabel("fresh")).toBe("Healthy");
    expect(marketEvidenceLabel("replay")).toBe("Replay");
    expect(marketEvidenceLabel("unknown")).toBe("Unavailable");
  });

  it("hides a measured win rate when there are no closed trades", () => {
    const empty = okSource({
      account: { current_equity: "1000" },
      metrics: { trade_count: 0, win_rate: 0, net_pnl: "0" },
    } as PaperPortfolioResponse);
    expect(portfolioWinRate(empty)).toEqual({
      value: UNAVAILABLE,
      note: "No closed trades yet",
    });
    expect(portfolioEquity(failedSource("down"))).toBe(UNAVAILABLE);
  });

  it("keeps unread alerts ahead of read alerts", () => {
    const alerts = importantAlerts(
      okSource({
        total: 2,
        items: [
          { id: "read", message: "Old", severity: "info", read_at: "2026-01-01T00:00:00Z", created_at: "2026-01-02T00:00:00Z" },
          { id: "new", message: "New", severity: "high", read_at: null, created_at: "2026-01-01T00:00:00Z" },
        ] as PaperAlert[],
      }),
    );
    expect(alerts?.map((item) => item.id)).toEqual(["new", "read"]);
  });
});
