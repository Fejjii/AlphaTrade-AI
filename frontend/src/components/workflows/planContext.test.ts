import { describe, expect, it } from "vitest";

import {
  lookupPlanSignalContext,
  parsePlanSignalContext,
} from "@/components/workflows/planContext";

describe("planContext lookup honesty", () => {
  it("returns ready context for valid tradingview deep links", () => {
    const params = new URLSearchParams("source=tradingview&signal=sig-1");
    expect(lookupPlanSignalContext(params)).toEqual({
      status: "ready",
      context: { source: "tradingview", signalId: "sig-1", alertId: undefined },
    });
    expect(parsePlanSignalContext(params)?.signalId).toBe("sig-1");
  });

  it("returns invalid instead of silently dropping bad source values", () => {
    const params = new URLSearchParams("source=garbage&signal=sig-1");
    const result = lookupPlanSignalContext(params);
    expect(result.status).toBe("invalid");
    if (result.status === "invalid") {
      expect(result.message).toMatch(/could not be applied/i);
    }
    expect(parsePlanSignalContext(params)).toBeNull();
  });

  it("returns none when no plan deep-link params are present", () => {
    expect(lookupPlanSignalContext(new URLSearchParams()).status).toBe("none");
  });
});
