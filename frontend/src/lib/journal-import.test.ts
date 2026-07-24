import { describe, expect, it } from "vitest";

import { autoDetectMapping, buildRows, parseCsv } from "@/lib/journal-import";

describe("parseCsv", () => {
  it("parses comma-separated rows with a header", () => {
    const parsed = parseCsv("symbol,side,pnl\nBTCUSDT,buy,12.5\nETHUSDT,sell,-3");
    expect(parsed.headers).toEqual(["symbol", "side", "pnl"]);
    expect(parsed.rows).toEqual([
      ["BTCUSDT", "buy", "12.5"],
      ["ETHUSDT", "sell", "-3"],
    ]);
  });

  it("handles quoted fields with embedded delimiters and doubled quotes", () => {
    const parsed = parseCsv('symbol,notes\nBTCUSDT,"swing, ""A+"" setup"');
    expect(parsed.rows[0]).toEqual(["BTCUSDT", 'swing, "A+" setup']);
  });

  it("auto-detects semicolon delimiters and skips empty lines", () => {
    const parsed = parseCsv("symbol;side\r\nBTCUSDT;long\r\n\r\nETHUSDT;short\r\n");
    expect(parsed.headers).toEqual(["symbol", "side"]);
    expect(parsed.rows).toHaveLength(2);
  });

  it("strips a UTF-8 BOM before the header", () => {
    const parsed = parseCsv("\uFEFFsymbol,side\nBTCUSDT,long");
    expect(parsed.headers[0]).toBe("symbol");
  });
});

describe("autoDetectMapping", () => {
  it("maps common exchange export headers to import fields", () => {
    const mapping = autoDetectMapping([
      "Pair",
      "Side",
      "Entry Price",
      "Close Time",
      "Qty",
      "Realized PnL",
      "Trade ID",
    ]);
    expect(mapping.symbol).toBe(0);
    expect(mapping.direction).toBe(1);
    expect(mapping.entry_price).toBe(2);
    expect(mapping.exit_time).toBe(3);
    expect(mapping.size).toBe(4);
    expect(mapping.net_pnl).toBe(5);
    expect(mapping.external_ref).toBe(6);
  });

  it("leaves unknown headers unmapped", () => {
    const mapping = autoDetectMapping(["foo", "bar"]);
    expect(Object.keys(mapping)).toHaveLength(0);
  });
});

describe("buildRows", () => {
  const parsed = parseCsv(
    [
      "symbol,side,entry_price,pnl,tags,opened",
      "btcusdt,buy,64500,496.8,swing;london,2026-06-01T10:00:00Z",
      "ETHUSDT,hold,not-a-number,-3,,bad-date",
    ].join("\n"),
  );
  const mapping = autoDetectMapping(parsed.headers);
  mapping.entry_time = 5;

  it("normalizes direction, symbol case, tags, and applies the default timeframe", () => {
    const { rows } = buildRows(parsed, mapping, { defaultTimeframe: "4h" });
    expect(rows[0]).toMatchObject({
      symbol: "BTCUSDT",
      direction: "long",
      timeframe: "4h",
      entry_price: "64500",
      net_pnl: "496.8",
      tags: ["swing", "london"],
      entry_time: "2026-06-01T10:00:00.000Z",
    });
  });

  it("flags malformed direction, numbers, and dates as row issues", () => {
    const { rows, issues } = buildRows(parsed, mapping, { defaultTimeframe: "1h" });
    expect(rows).toHaveLength(2);
    expect(issues).toHaveLength(1);
    expect(issues[0].index).toBe(1);
    const combined = issues[0].messages.join(" | ");
    expect(combined).toContain("direction");
    expect(combined).toContain("entry_price");
    expect(combined).toContain("entry_time");
  });

  it("parses epoch timestamps in seconds and milliseconds", () => {
    const epochParsed = parseCsv("symbol,side,opened\nBTCUSDT,long,1750000000");
    const epochMapping = autoDetectMapping(epochParsed.headers);
    epochMapping.entry_time = 2;
    const { rows, issues } = buildRows(epochParsed, epochMapping, { defaultTimeframe: "1h" });
    expect(issues).toHaveLength(0);
    expect(rows[0].entry_time).toBe(new Date(1750000000 * 1000).toISOString());
  });
});
