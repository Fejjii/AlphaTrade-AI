import { describe, expect, it } from "vitest";

import { buildInboxSignals } from "@/components/workflows/buildInboxSignals";
import type { TradingViewSignalItem } from "@/lib/api/types";

const baseSignal = {
  id: "sig-1",
  organization_id: "org",
  external_alert_id: "tv-1",
  idempotency_key: "tv-1",
  status: "validated",
  symbol: "BTCUSDT",
  timeframe: "15m",
  direction: "long",
  setup_name: "Pullback",
  setup_version: 1,
  setup_definition_id: null,
  strategy_id: null,
  strategy_version_id: null,
  trigger_level: 1,
  invalidation_level: 2,
  take_profit_level: 3,
  stop_loss_level: 2,
  confidence: 0.8,
  source_metadata: { source: "tradingview" },
  validation_errors: null,
  rejection_reason: null,
  received_at: "2026-07-26T11:58:00.000Z",
  validated_at: "2026-07-26T11:58:01.000Z",
  occurred_at: null,
  duplicate_of_signal_id: null,
  links: {
    setup_definition_id: null,
    strategy_id: null,
    strategy_version_id: null,
    source_alert_id: null,
    draft_id: null,
    candidate_id: null,
    journal_trade_id: null,
    backtest_run_id: null,
    paper_candidate_path: null,
    strategy_path: null,
    journal_path: null,
  },
  note: "paper only",
} satisfies TradingViewSignalItem;

describe("buildInboxSignals", () => {
  const nowMs = Date.parse("2026-07-26T12:00:00.000Z");

  it("preserves source, provenance, freshness, and next actions", () => {
    const items = buildInboxSignals({
      nowMs,
      tradingViewSignals: [baseSignal],
      alerts: [
        {
          id: "a1",
          alert_type: "setup_signal_detected",
          severity: "warning",
          message: "Setup found",
          created_at: "2026-07-26T11:58:00.000Z",
          alert_source: "market_watcher",
        },
      ],
      setupReviews: [
        {
          alert_id: "r1",
          created_at: "2026-07-26T11:57:00.000Z",
          symbol: "ETHUSDT",
          timeframe: "1h",
          condition: "order_block",
          direction: "long",
          confidence: 0.9,
          reason: "OB reclaim",
          trigger_level: null,
          invalidation_level: null,
          latest_price: null,
          delivery_channel: "in_app",
          delivery_status: "delivered",
          dedupe_key: null,
          review_status: "unreviewed",
          review_notes: null,
          reviewed_at: null,
        },
      ],
    });

    const tv = items.find((item) => item.source === "tradingview");
    expect(tv?.freshness).toBe("live");
    expect(tv?.provenance).toContain("TradingView");
    expect(tv?.nextAction).toBe("Create paper candidate");
    expect(tv?.canCreateDraft).toBe(true);
    expect(tv?.createActionLabel).toBe("Create paper candidate");
    expect(tv?.canHideForSession).toBe(true);
    expect(tv?.canDismissWithReason).toBe(false);
    expect(tv?.planHref).toBe("/workspace?source=tradingview&signal=sig-1");

    const alert = items.find((item) => item.source === "alert");
    expect(alert?.provenance).toContain("market_watcher");
    expect(alert?.freshness).toBe("live");
    expect(alert?.canDismissWithReason).toBe(true);

    const setup = items.find((item) => item.source === "setup_review");
    expect(setup?.reviewStatus).toBe("needs_review");
    expect(setup?.href).toBe("/alerts/review");
    expect(setup?.createActionLabel).toBe("Create validation draft");
    expect(setup?.planHref).toContain("source=setup_review");
  });

  it("distinguishes stale timestamps without fabricating live status", () => {
    const items = buildInboxSignals({
      nowMs,
      tradingViewSignals: [
        {
          ...baseSignal,
          received_at: "2026-07-26T10:00:00.000Z",
        },
      ],
    });
    expect(items[0]?.freshness).toBe("stale");
  });
});
