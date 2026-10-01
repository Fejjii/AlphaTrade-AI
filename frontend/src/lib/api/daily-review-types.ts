export type ReviewTopic =
  | "watcher_activity" | "setups" | "paper_opened" | "paper_closed"
  | "blocked_candidates" | "risk_events" | "journal_entries" | "mistakes"
  | "lessons" | "missed_setups" | "strategy_observations" | "data_quality_limitations";

export type ReviewSource = {
  record_type: string;
  record_id: string;
  occurred_at: string;
  version: number | null;
  content_hash: string | null;
  upstream_system: string | null;
  upstream_event_id: string | null;
};

export type ReviewItem = {
  topic: ReviewTopic;
  classification: "fact" | "user_observation" | "system_inference" | "research_suggestion";
  code: string;
  text: string | null;
  sources: ReviewSource[];
  candidate_id: string | null;
  strategy_version_id: string | null;
};

export type DailyReview = {
  schema_version: "DailyReview/v1";
  review_id: string;
  content_hash: string;
  organization_id: string;
  user_id: string;
  window: { day: string; timezone: string; start: string; end: string };
  generated_at: string;
  facts: ReviewItem[];
  user_observations: ReviewItem[];
  system_inference: ReviewItem[];
  research_suggestions: ReviewItem[];
  counts: Record<ReviewTopic, number>;
  daily_pnl: {
    cohort: string;
    closed_count: number;
    measured_count: number;
    missing_pnl_count: number;
    recorded_net_pnl: string | null;
    complete: boolean;
    wins: number;
    losses: number;
    breakeven: number;
    minimum_sample: number;
    win_rate: string | null;
    expectancy: string | null;
    sources: ReviewSource[];
  }[];
  limitations: string[];
  live_executable: false;
  telegram_delivery: false;
};
