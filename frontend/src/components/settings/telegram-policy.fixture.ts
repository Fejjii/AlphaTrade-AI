import type { TelegramNotificationPolicyV2 } from "@/lib/api/types";

/** Backend-shaped fixture: explicit null means all, [] means none. */
export const telegramPolicyFixture: TelegramNotificationPolicyV2 = {
  schema_version: 2,
  strategy_subscriptions: null,
  symbol_subscriptions: ["BTCUSDT"],
  setup_stages: ["N2", "N3"],
  event_types: ["SETUP", "RISK", "STOP"],
  severities: ["WATCH", "ACTION", "CRITICAL"],
  minimum_severity: "WATCH",
  minimum_quality: null,
  forming_alerts: false,
  confirmed_alerts: true,
  risk_alerts: true,
  paper_trade_opened: true,
  paper_trade_closed: true,
  stop_event: true,
  partial_profit_event: true,
  daily_review_event: false,
  cooldown_seconds: 120,
  duplicate_suppression_seconds: 86400,
  quiet_hours: { start: "22:00", end: "07:00", timezone: "Europe/Berlin" },
};
