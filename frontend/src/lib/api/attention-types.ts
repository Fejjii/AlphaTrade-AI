import type { ReviewSource } from "./daily-review-types";

export interface AttentionItem {
  item_id: string;
  category: "risk_block" | "risk_event" | "provider_outage" | "missing_evidence"
    | "stale_evidence" | "telegram_delivery_failure" | "watcher_state"
    | "confirmed_setup" | "forming_setup" | "paper_position"
    | "strategy_proposal_pending" | "strategy_validation_job" | "replay_result"
    | "daily_review_lesson";
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  reason: string;
  sources: ReviewSource[];
  symbol: string | null;
  strategy_id: string | null;
  strategy_version_id: string | null;
  recommended_next_action: string | null;
  expires_at: string | null;
  acknowledgement_state: "unsupported" | "unacknowledged" | "acknowledged";
}

export interface AttentionQueue {
  schema_version: "AttentionQueue/v1";
  organization_id: string;
  user_id: string;
  generated_at: string;
  items: AttentionItem[];
  recommended_next_action: string | null;
  limitations: string[];
  execution_mode: "paper";
  executes_trades: false;
  approves_strategies: false;
  bypasses_risk: false;
  telegram_delivery: false;
}
