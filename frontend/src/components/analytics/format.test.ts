import { describe, expect, it } from "vitest";

import {
  containsCurrencySymbol,
  formatMonetary,
  formatPercent,
  formatProfitFactor,
  formatTrendLabel,
} from "./format";

describe("analytics format", () => {
  it("formats monetary values without currency symbols", () => {
    expect(formatMonetary("123.456")).toBe("+123.46");
    expect(formatMonetary("-45")).toBe("−45.00");
    expect(formatMonetary(null)).toBe("—");
    expect(containsCurrencySymbol(formatMonetary("100"))).toBe(false);
  });

  it("formats percent and profit factor honestly", () => {
    expect(formatPercent(0.5123)).toBe("51.2%");
    expect(formatPercent(null)).toBe("—");
    expect(formatProfitFactor(null, ["no_losing_trades"])).toBe("n/a — no losing trades");
    expect(formatProfitFactor(1.8)).toBe("1.80");
    expect(formatTrendLabel("insufficient_data")).toBe("Insufficient data");
  });
});
