/** Typed models mirroring backend Pydantic schemas. */

export type RiskSeverity = "info" | "low" | "medium" | "high" | "critical";
export type TradeDirection = "long" | "short";
export type ProposalStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "expired"
  | "executed"
  | "cancelled";
export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "modified"
  | "paused"
  | "cancelled"
  | "closed"
  | "needs_more_analysis";
export type PositionStatus = "open" | "closed" | "liquidated";
export type Timeframe =
  | "1m"
  | "3m"
  | "5m"
  | "15m"
  | "30m"
  | "1h"
  | "2h"
  | "4h"
  | "6h"
  | "12h"
  | "1d"
  | "3d"
  | "1w";
export type StrategyId =
  | "htf_trend_pullback"
  | "liquidity_sweep_reversal"
  | "countertrend_short_build"
  | "passive_level_order"
  | "profit_protection"
  | "green_day_guard"
  | "mental_capital_guard"
  | "manual_review";
export type DocumentSourceType =
  | "playbook"
  | "journal"
  | "market_note"
  | "strategy_doc"
  | "risk_policy"
  | "external";
export type AuditSeverity = "info" | "warning" | "error" | "critical";
export type AuditEventType = string;
export type ProviderKind =
  | "llm"
  | "embeddings"
  | "vector"
  | "exchange"
  | "market_data"
  | "news"
  | "notifications"
  | "tracing"
  | "email";
export type ProviderHealth = "healthy" | "degraded" | "unavailable";

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
  execution_mode: string;
  real_trading_enabled: boolean;
  must_verify_email: boolean;
  demo_seed_enabled?: boolean;
  timestamp: string;
}

export interface ReadinessResponse {
  status: string;
  ready: boolean;
  providers_total: number;
  providers_unavailable: number;
  timestamp: string;
}

export interface ProviderStatus {
  name: string;
  kind: ProviderKind;
  health: ProviderHealth;
  using_fallback: boolean;
  is_mock: boolean;
  detail?: string | null;
  last_success_at?: string | null;
  error_message?: string | null;
}

export interface ProviderStatusResponse {
  generated_at: string;
  providers: ProviderStatus[];
}

export interface TakeProfitLevel {
  price: string;
  size_fraction: number;
}

export interface ExitCriteria {
  invalidation: string;
  stop_loss: string;
  take_profits: TakeProfitLevel[];
  breakeven_trigger?: string | null;
  runner_enabled?: boolean;
  runner_notes?: string | null;
}

export interface RiskCheckResult {
  action: "allow" | "warn" | "block";
  severity: RiskSeverity;
  triggered_rules: Array<{
    rule_id: string;
    action: string;
    severity: RiskSeverity;
    message: string;
  }>;
  summary: string;
}

export interface TradeProposal {
  id: string;
  organization_id: string;
  user_id: string;
  signal_id?: string | null;
  strategy_id: StrategyId;
  symbol: string;
  timeframe: Timeframe;
  direction: TradeDirection;
  entry_price: string;
  entry_low?: string | null;
  entry_high?: string | null;
  position_size: string;
  leverage: string;
  exit: ExitCriteria;
  confidence: number;
  risk_level: RiskSeverity;
  rationale: string;
  status: ProposalStatus;
  approval_required: boolean;
  risk_result?: RiskCheckResult | null;
  loss_acceptance_required?: boolean;
  loss_acceptance_status?: string;
  planned_loss_amount?: string | null;
  created_at: string;
}

export interface PaginatedTradeProposals {
  items: TradeProposal[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApprovalRequest {
  id: string;
  proposal_id: string;
  organization_id: string;
  user_id: string;
  status: ApprovalStatus;
  proposed_action?: string | null;
  modified_fields?: Record<string, string> | null;
  risk_level: RiskSeverity;
  confidence: number;
  approval_reason?: string | null;
  audit_event_id?: string | null;
  created_at: string;
  decided_at?: string | null;
}

export interface PaginatedApprovalRequests {
  items: ApprovalRequest[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProposalWorkflowView {
  proposal: TradeProposal;
  approval: ApprovalRequest | null;
  can_execute_paper: boolean;
  block_reason: string | null;
}

export interface ApprovalWorkflowView {
  approval: ApprovalRequest;
  proposal: TradeProposal | null;
  can_execute_paper: boolean;
  block_reason: string | null;
}

export interface Position {
  id: string;
  organization_id: string;
  user_id: string;
  symbol: string;
  direction: TradeDirection;
  size: string;
  entry_price: string;
  leverage: string;
  stop_loss?: string | null;
  take_profits: TakeProfitLevel[];
  liquidation_price?: string | null;
  unrealized_pnl: string;
  realized_pnl: string;
  risk_state: Record<string, string>;
  status: PositionStatus;
  opened_at: string;
  closed_at?: string | null;
}

export interface PaginatedPositions {
  items: Position[];
  total: number;
  limit: number;
  offset: number;
}

export interface WatchlistItem {
  id: string;
  organization_id: string;
  user_id: string;
  symbol: string;
  exchange: string;
  timeframes: Timeframe[];
  strategy_ids: StrategyId[];
  enabled: boolean;
  created_at: string;
}

export interface JournalEntry {
  id: string;
  organization_id: string;
  user_id: string;
  symbol: string;
  timeframe: Timeframe;
  direction: TradeDirection;
  strategy_id?: StrategyId | null;
  entry_rationale: string;
  exit_rationale?: string | null;
  emotions: string[];
  mistakes: string[];
  lessons?: string | null;
  improvement_rule?: string | null;
  result: string;
  pnl?: string | null;
  stress_score?: number | null;
  tags: string[];
  screenshot_refs: string[];
  linked_proposal_id?: string | null;
  linked_position_id?: string | null;
  rag_synced?: boolean;
  created_at: string;
}

export interface SetupStatistics {
  setup_type: StrategyId;
  proposal_count: number;
  paper_trade_count: number;
  winning_paper_trades: number;
  losing_paper_trades: number;
  average_paper_pnl?: string | null;
  average_risk_level?: string | null;
  average_confidence?: number | null;
  most_common_mistakes: string[];
  most_common_lessons: string[];
  last_used_at?: string | null;
}

export interface SetupAnalyticsResponse {
  organization_id: string;
  user_id: string;
  setup_type_filter?: StrategyId | null;
  date_range: { start?: string | null; end?: string | null };
  setups: SetupStatistics[];
}

export interface TradeReviewAnalytics {
  total_journaled_trades: number;
  win_count: number;
  loss_count: number;
  average_pnl?: string | null;
  most_frequent_setup_type?: StrategyId | null;
  most_frequent_mistake_tag?: string | null;
  most_frequent_emotion_tag?: string | null;
  trades_after_daily_loss_warning: number;
  trades_after_green_day_warning: number;
  trades_blocked_by_risk_engine: number;
  proposals_rejected_by_user: number;
  proposals_needing_more_analysis: number;
}

export interface DisciplineScoreResult {
  score: number;
  grade: string;
  positive_behaviors: string[];
  negative_behaviors: string[];
  improvement_suggestions: string[];
}

export interface RiskBehaviorAnalytics {
  risk_blocks_count: number;
  daily_loss_warnings: number;
  green_day_warnings: number;
  overtrading_warnings: number;
  revenge_trading_warnings: number;
  proposals_rejected: number;
  proposals_needs_more_analysis: number;
  paper_orders_rejected: number;
  approval_pending_count: number;
  approval_approved_count: number;
  journal_completion_rate: number;
  triggered_rules: Record<string, number>;
}

export interface DashboardSafetyStatus {
  execution_mode: string;
  paper_only: boolean;
  real_trading_enabled: boolean;
  real_trading_disabled: boolean;
}

export interface DailyDisciplineSnapshot {
  date: string;
  timezone: string;
  trades_today: number;
  paper_trades_opened_today: number;
  paper_trades_closed_today: number;
  journal_entries_today: number;
  realized_pnl_today_paper: string | null;
  unrealized_pnl_paper: string | null;
  net_pnl_today_paper: string | null;
  daily_loss_limit: string | null;
  daily_target: string | null;
  loss_lock_active: boolean;
  green_day_protection_active: boolean;
  overtrading_warning_active: boolean;
  max_trades_per_day: number | null;
  remaining_trades_allowed: number | null;
  discipline_status: "calm" | "caution" | "locked" | "review_only" | string;
  risk_settings_source: "configured_daily_state" | "user_risk_settings" | "system_default" | string;
  pnl_sources: Record<string, string | null>;
  reasons: string[];
  recommended_action: string;
  limitations: string[];
}

export interface StrategyReadinessCounts {
  needs_structure: number;
  ready_for_backtest: number;
  needs_more_sample: number;
  paper_eligible: number;
  paper_validation_running: number;
  paper_validated: number;
  restricted: number;
}

export interface StrategyActionItem {
  strategy_id: string;
  name: string;
  status: string;
  next_action: string;
  blockers: string[];
  link_hint: string;
}

export interface StrategyReadinessSummary {
  counts: StrategyReadinessCounts;
  top_needing_action: StrategyActionItem[];
  limitations: string[];
}

export interface ActivePaperValidationItem {
  strategy_id: string;
  name: string;
  status: string;
}

export interface OpenPaperTradeItem {
  position_id: string | null;
  paper_trade_id?: string | null;
  strategy_id?: string | null;
  strategy_name?: string | null;
  symbol: string;
  direction: string;
  unrealized_pnl: string | null;
  status: string;
  source?: string;
}

export interface DisciplineScoreSummary {
  score: number | null;
  grade: string | null;
  band: "strong" | "good" | "caution" | "review_needed" | string | null;
  main_contributors: string[];
  limitations: string[];
}

export interface OpenPaperTradesSummary {
  proposal_flow_count: number;
  paper_validation_count: number;
  total_count: number;
  total_open_exposure: string | null;
  items: OpenPaperTradeItem[];
  limitations: string[];
}

export interface UserRiskSettings {
  organization_id: string;
  user_id: string;
  daily_loss_limit: string | null;
  daily_target: string | null;
  max_trades_per_day: number;
  max_risk_per_trade_percent: string;
  default_account_balance: string;
  timezone: string;
  green_day_protection_enabled: boolean;
  one_loss_stop_enabled: boolean;
  overtrading_guard_enabled: boolean;
  notes: string | null;
  using_defaults: boolean;
  timezone_fallback: boolean;
}

export interface UserRiskSettingsUpdate {
  daily_loss_limit?: string | null;
  daily_target?: string | null;
  max_trades_per_day?: number;
  max_risk_per_trade_percent?: string;
  default_account_balance?: string;
  timezone?: string;
  green_day_protection_enabled?: boolean;
  one_loss_stop_enabled?: boolean;
  overtrading_guard_enabled?: boolean;
  notes?: string | null;
}

export interface AlertSummaryItem {
  alert_type: string;
  severity: string;
  message: string;
}

export interface AlertsLessonsSummary {
  unread_alerts: number;
  latest_high_priority: AlertSummaryItem[];
  pending_lessons: number;
  accepted_lessons: number;
  top_pending_lessons: string[];
  limitations: string[];
}

export interface NextRecommendedAction {
  action: string;
  reason: string;
  link: string;
  priority: number;
}

export interface DashboardSummary {
  safety: DashboardSafetyStatus;
  daily_discipline: DailyDisciplineSnapshot | null;
  discipline_score: DisciplineScoreSummary | null;
  strategy_readiness: StrategyReadinessSummary | null;
  active_paper_validations: ActivePaperValidationItem[];
  open_paper_trades: OpenPaperTradeItem[];
  open_paper_trades_summary: OpenPaperTradesSummary | null;
  alerts_lessons: AlertsLessonsSummary | null;
  market_watcher: {
    effective_enabled: boolean;
    last_scan_at: string | null;
    fresh_observations: number;
    limitations: string[];
  } | null;
  bridge: {
    effective_enabled: boolean;
    last_tick_at: string | null;
    scans_triggered_last_tick: number;
    limitations: string[];
  } | null;
  next_recommended_action: NextRecommendedAction;
  limitations: string[];
}

export interface PaginatedJournalEntries {
  items: JournalEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface Citation {
  document_id: string;
  chunk_id: string;
  title?: string | null;
  source_type: DocumentSourceType;
  section_title?: string | null;
  page_number?: number | null;
  chunk_ordinal?: number | null;
  score?: number | null;
  snippet?: string | null;
}

export interface RetrievedChunk {
  chunk_id: string;
  document_id: string;
  title?: string | null;
  section_title?: string | null;
  page_number?: number | null;
  chunk_ordinal: number;
  source_type: DocumentSourceType;
  content: string;
  score: number;
}

export interface RagSearchResponse {
  query: string;
  chunks: RetrievedChunk[];
  citations: Citation[];
}

export interface IngestDocumentResponse {
  document_id: string;
  source_hash: string;
  chunk_count: number;
  duplicate: boolean;
  version: number;
}

export interface UsageSummary {
  organization_id?: string | null;
  user_id?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  event_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_provider_reported_cost: string;
  total_estimated_cost: string;
  total_cost: string;
  billing_grade_cost: string;
  cost_is_placeholder: boolean;
  total_tool_calls: number;
  fallback_count: number;
  cache_hit_count: number;
}

export interface UsageEvent {
  usage_event_id?: string | null;
  request_id?: string | null;
  organization_id?: string | null;
  user_id?: string | null;
  feature: string;
  model?: string | null;
  provider?: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  provider_reported_cost?: string | null;
  estimated_cost: string;
  cost_source: string;
  cost_is_placeholder: boolean;
  is_billing_grade?: boolean;
  tool_calls: number;
  cache_hit: boolean;
  fallback_used: boolean;
  latency_ms?: number | null;
  status: string;
  timestamp: string;
}

export interface UsageFeatureBreakdown {
  feature: string;
  event_count: number;
  total_tokens: number;
  total_cost: string;
  fallback_count: number;
}

export interface UsageProviderBreakdown {
  provider: string;
  event_count: number;
  total_tokens: number;
  total_cost: string;
  fallback_count: number;
}

export interface OrganizationQuotaConfig {
  organization_id: string;
  monthly_token_limit: number;
  monthly_cost_limit: string;
  daily_request_limit: number;
  limit_agent_chat: number;
  limit_rag_ingest: number;
  limit_market_analyze: number;
  limit_agent_narrative: number;
  limit_paper_execution: number;
  soft_warning_threshold: string;
  hard_block_threshold: string;
}

export interface QuotaUsageSnapshot {
  monthly_tokens_used: number;
  monthly_tokens_limit: number;
  monthly_tokens_pct: number;
  monthly_cost_used: string;
  monthly_cost_limit: string;
  monthly_cost_pct: number;
  daily_requests_used: number;
  daily_requests_limit: number;
  daily_requests_pct: number;
  feature_usage: Record<string, number>;
}

export interface QuotaStatus {
  quota: OrganizationQuotaConfig;
  usage: QuotaUsageSnapshot;
  soft_limit_reached: boolean;
  hard_limit_reached: boolean;
  warnings: string[];
  blocked_features: string[];
}

export interface PaginatedUsageEvents {
  items: UsageEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface SubscriptionPlan {
  plan_id: string;
  name: string;
  description: string;
  monthly_token_limit: number;
  monthly_cost_limit: string;
  daily_request_limit: number;
  limit_agent_chat: number;
  limit_rag_ingest: number;
  limit_market_analyze: number;
  limit_agent_narrative: number;
  limit_paper_execution: number;
  seat_limit: number;
  price_display: string;
  price_currency: string;
  stripe_price_id?: string | null;
}

export interface BillingCustomer {
  id: string;
  organization_id: string;
  provider: string;
  provider_customer_id: string;
  billing_email: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BillingSubscription {
  id: string;
  organization_id: string;
  provider_subscription_id: string | null;
  plan_id: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  created_at: string;
  updated_at: string;
}

export interface BillingStatus {
  billing_enabled: boolean;
  provider: string;
  is_mock: boolean;
  live_checkout_available: boolean;
  current_plan_id: string;
  customer: BillingCustomer | null;
  subscription: BillingSubscription | null;
}

export interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
  is_mock: boolean;
}

export interface PortalResponse {
  portal_url: string;
  is_mock: boolean;
}

export interface UsageExportResponse {
  batch_id: string;
  organization_id: string;
  period_start: string;
  period_end: string;
  total_events: number;
  total_tokens: number;
  provider_reported_cost: string;
  estimated_cost: string;
  billing_grade_cost: string;
  cost_is_billing_grade: boolean;
  fallback_event_count: number;
  line_items: Array<{
    feature: string;
    event_count: number;
    total_tokens: number;
    provider_reported_cost: string;
    estimated_cost: string;
    cost_is_billing_grade: boolean;
  }>;
  provider: string;
  exported_at: string;
}

export interface AuditRecord {
  event_id: string;
  request_id: string;
  trace_id: string;
  user_id?: string | null;
  organization_id?: string | null;
  event_type: AuditEventType;
  resource_type: string;
  resource_id?: string | null;
  actor_type: string;
  action: string;
  result: string;
  severity: AuditSeverity;
  payload_hash: string;
  redacted_metadata: Record<string, unknown>;
  timestamp: string;
}

export interface PaginatedAuditRecords {
  items: AuditRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface ToolOutput {
  tool_name: string;
  success: boolean;
  result?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  used_fallback: boolean;
  error?: string | null;
  latency_ms?: number | null;
}

export interface TradingAnalysisDetail {
  summary: string;
  setup_type?: string | null;
  evidence: string[];
  risk_level?: RiskSeverity | null;
  confidence?: number | null;
  invalidation?: string | null;
  stop_loss_or_no_trade_reason: string;
  approval_status: string;
  next_decision_point?: string | null;
  paper_mode_disclaimer?: string | null;
  market_data_quality: string;
}

export interface TradingNarrativeDetail {
  summary: string;
  setup_interpretation: string;
  evidence_explanation: string;
  risk_explanation: string;
  invalidation_explanation: string;
  next_decision_point: string;
  caution_notes: string[];
  limitations: string[];
  paper_mode_disclaimer: string;
  citations_used: string[];
}

export interface NarrativeMetadata {
  source: string;
  provider: string;
  model: string;
  fallback_used: boolean;
  validation_passed: boolean;
  latency_ms?: number | null;
}

export interface AgentMessageResponse {
  conversation_id: string;
  request_id: string;
  reply: string;
  risk_level?: RiskSeverity | null;
  confidence?: number | null;
  approval_required: boolean;
  approval_status: string;
  approval_reason?: string | null;
  proposal_id?: string | null;
  approval_id?: string | null;
  citations: Citation[];
  tool_outputs: ToolOutput[];
  risk_result?: RiskCheckResult | null;
  limitations: string[];
  usage?: UsageEvent | null;
  analysis?: TradingAnalysisDetail | null;
  narrative?: TradingNarrativeDetail | null;
  narrative_meta?: NarrativeMetadata | null;
}

export interface PaperOrder {
  id: string;
  proposal_id?: string | null;
  symbol: string;
  side: string;
  status: string;
  quantity: string;
  filled_price?: string | null;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  role: string;
  risk_profile: string;
  timezone: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface MessageResponse {
  message: string;
}

export type MembershipRole = "owner" | "trader" | "viewer";

export interface OrganizationInvitation {
  id: string;
  organization_id: string;
  email: string;
  role: MembershipRole;
  invited_by_user_id: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
  is_pending: boolean;
}

export interface InvitationListResponse {
  invitations: OrganizationInvitation[];
}

export interface Organization {
  id: string;
  name: string;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  organization: Organization;
  tokens: TokenPair;
}

export interface MeResponse {
  user: User;
  organization: Organization;
}

export interface MarketDataMeta {
  symbol: string;
  exchange: string;
  timeframe?: Timeframe | null;
  timestamp: string;
  source: string;
  is_live: boolean;
  is_stale: boolean;
  stale_reason?: string | null;
  provider_name: string;
  fallback_used: boolean;
  retrieved_at: string;
  cache_hit?: boolean;
}

export interface TickerResponse {
  meta: MarketDataMeta;
  last_price: string;
  bid?: string | null;
  ask?: string | null;
  volume_24h?: string | null;
  change_24h_pct?: number | null;
}

export interface OHLCVBar {
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  timestamp: string;
}

export interface OHLCVResponse {
  meta: MarketDataMeta;
  bars: OHLCVBar[];
}

export interface IndicatorContext {
  symbol: string;
  timeframe: Timeframe;
  rsi?: number | null;
  vwap?: string | null;
  ema_fast?: string | null;
  ema_slow?: string | null;
  macd?: number | null;
  macd_signal?: number | null;
  atr?: string | null;
  volatility?: number | null;
  volume_trend?: number | null;
  funding_rate?: string | null;
  timestamp: string;
}

export interface MarketSnapshotResponse {
  meta: MarketDataMeta;
  ticker?: TickerResponse | null;
  latest_bar?: OHLCVBar | null;
  indicators?: IndicatorContext | null;
  funding_rate?: string | null;
}

export interface StrategySignalSummary {
  strategy_id: StrategyId;
  direction?: string | null;
  confidence?: number | null;
  evidence: string[];
  data_quality_note?: string | null;
}

export interface MarketAnalyzeResponse {
  snapshot: MarketSnapshotResponse;
  indicators: IndicatorContext;
  strategy_signals: StrategySignalSummary[];
  data_quality: string;
  confidence_penalty_applied: boolean;
}

export type ManualLevelType =
  | "support"
  | "resistance"
  | "fibonacci"
  | "trend_line"
  | "vwap"
  | "liquidity_zone"
  | "previous_high"
  | "previous_low"
  | "user_note";

export type PreTradeRecommendation =
  | "no_trade"
  | "watch"
  | "small_probe"
  | "normal_size"
  | "high_conviction";

export interface StrategyCard {
  strategy_name: string;
  market_type: string;
  asset_universe: string[];
  timeframes: Timeframe[];
  entry_conditions: string[];
  confirmation_conditions: string[];
  invalidation: string[];
  stop_loss: string[];
  take_profit_plan: string[];
  runner_plan: string[];
  position_sizing: string[];
  add_rules: string[];
  no_trade_rules: string[];
  backtest_rules: string[];
  success_criteria: string[];
  validation_status: string;
}

export interface UserStrategy {
  id: string;
  name: string;
  setup_type: StrategyId;
  current_version: number;
  enabled: boolean;
  notes?: string | null;
  latest_card?: StrategyCard | null;
  validation_status?: string | null;
  backtest_status?: string | null;
  paper_validation_status?: string | null;
  paper_eligible?: boolean;
  created_at: string;
  updated_at: string;
}

export interface BacktestMetrics {
  trade_count: number;
  win_rate: number;
  profit_factor: number;
  expectancy: string;
  max_drawdown_pct: number;
  average_win: string;
  average_loss: string;
  largest_win: string;
  largest_loss: string;
  consecutive_losses: number;
  average_time_in_trade_bars: number;
  total_fees: string;
  total_slippage: string;
  net_pnl: string;
  return_pct: number;
  ending_equity: string;
  symbol: string;
  timeframe: string;
}

export interface BacktestResult {
  metrics: BacktestMetrics;
  recommendation: string;
  meets_success_criteria?: boolean;
  limitations?: string[];
  data_quality?: string;
  note?: string;
}

export interface BacktestTrade {
  entry_time: string;
  exit_time: string;
  direction: string;
  entry_price: string;
  exit_price: string;
  net_pnl: string;
  exit_reason: string;
}

export interface BacktestRun {
  id: string;
  strategy_id: string;
  status: string;
  assumptions: Record<string, unknown>;
  result?: BacktestResult | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedBacktestTrades {
  items: BacktestTrade[];
  total: number;
  limit: number;
  offset: number;
}

export interface PaperValidationMetrics {
  paper_trades_count: number;
  win_rate: number;
  net_pnl: string;
  gross_pnl?: string;
  profit_factor: number;
  expectancy: string;
  max_drawdown_pct: number;
  total_fees?: string;
  total_slippage?: string;
  average_win?: string;
  average_loss?: string;
  consecutive_losses?: number;
  average_holding_time_hours?: number;
  plan_adherence_avg?: number | null;
  early_exit_count?: number;
  stop_respected_count?: number;
  runner_helped_count?: number;
}

export interface PaperValidationRun {
  id: string;
  strategy_id: string;
  strategy_version_id?: string | null;
  status: string;
  runtime_mode?: string;
  paper_eligible: boolean;
  config?: Record<string, unknown> | null;
  blockers?: string[];
  last_scan_at?: string | null;
  last_tick_at?: string | null;
  last_scan_result?: Record<string, unknown> | null;
  metrics?: PaperValidationMetrics | null;
  recommendation?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaperSignalResult {
  id: string;
  triggered: boolean;
  status: string;
  symbol: string;
  direction: string;
  confidence: number;
  suggested_entry?: string | null;
  stop_loss?: string | null;
  reason?: string | null;
  created_at: string;
}

export interface PaperTradeRecord {
  id: string;
  status: string;
  symbol: string;
  direction: string;
  entry_price?: string | null;
  exit_price?: string | null;
  net_pnl?: string | null;
  exit_reason?: string | null;
  created_at: string;
}

export interface PaperScanResult {
  run_id: string;
  signal?: PaperSignalResult | null;
  trade_created: boolean;
  blockers: string[];
  scanned_at: string;
}

export interface PaperTickResult {
  run_id: string;
  trades_closed: number;
  trades_open: number;
  metrics?: PaperValidationMetrics | null;
  recommendation?: string | null;
  ticked_at: string;
}

export interface PaperValidationSummary {
  strategy_id: string;
  paper_eligible: boolean;
  latest_status?: string | null;
  runs: PaperValidationRun[];
  total: number;
  limitation?: string;
}

export interface PaperSchedulerStatus {
  env_enabled: boolean;
  tenant_enabled: boolean;
  effective_enabled: boolean;
  config: {
    enabled: boolean;
    interval_seconds: number;
    max_runs_per_cycle: number;
    max_scans_per_minute: number;
  };
  last_tick_at?: string | null;
  last_tick_status?: string | null;
  real_trading_enabled: boolean;
  limitation: string;
}

export interface PaperSchedulerTickResult {
  ticked_at: string;
  env_enabled: boolean;
  effective_enabled: boolean;
  runs_processed: number;
  runs_skipped: number;
  scans_executed: number;
  ticks_executed: number;
  alerts_created: number;
  decisions: string[];
  limitation: string;
}

export interface PaperRuntimeHistoryRecord {
  id: string;
  run_id?: string | null;
  strategy_id?: string | null;
  symbol?: string | null;
  mode: string;
  started_at: string;
  completed_at?: string | null;
  status: string;
  reason?: string | null;
  signals_created: number;
  trades_opened: number;
  trades_closed: number;
  blockers: string[];
  warnings: string[];
  data_freshness?: string | null;
  latency_ms?: number | null;
}

export interface PaperAlert {
  id: string;
  alert_type: string;
  severity: string;
  strategy_id?: string | null;
  paper_validation_run_id?: string | null;
  paper_trade_id?: string | null;
  message: string;
  read_at?: string | null;
  delivery_status?: string;
  delivery_channel?: string;
  delivery_attempts?: number;
  last_delivery_error?: string | null;
  delivered_at?: string | null;
  next_retry_at?: string | null;
  delivery_skipped_reason?: string | null;
  retry_exhausted?: boolean;
  alert_source?: string;
  created_at: string;
}

export interface AlertDeliveryStatusResponse {
  delivery_enabled: boolean;
  webhook_enabled: boolean;
  telegram_enabled: boolean;
  email_enabled: boolean;
  push_enabled: boolean;
  webhook_configured: boolean;
  telegram_configured?: boolean;
  effective_external_enabled: boolean;
  channels: string[];
  channel_statuses?: ChannelProviderStatus[];
  paper_only: boolean;
  limitations?: string[];
}

export interface ChannelProviderStatus {
  channel: string;
  env_enabled: boolean;
  user_enabled: boolean;
  configured: boolean;
  available: boolean;
  status_label: string;
}

export interface NotificationPreferences {
  in_app_enabled: boolean;
  webhook_enabled: boolean;
  telegram_enabled: boolean;
  min_severity: string;
  enabled_alert_types?: string[] | null;
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  timezone?: string;
  digest_mode?: string;
  telegram_chat_id?: string | null;
  using_defaults?: boolean;
}

export interface NotificationTestResult {
  success: boolean;
  message: string;
  channels_attempted: string[];
  channels_succeeded: string[];
  channels_skipped: string[];
  errors: Record<string, string>;
  paper_only: boolean;
  test_label: string;
}

export interface MarketWatcherStatus {
  env_enabled: boolean;
  effective_enabled: boolean;
  watched_symbols: string[];
  last_scan_at?: string | null;
  paper_only: boolean;
  real_trading_enabled: boolean;
}

export interface MarketWatcherScanResult {
  scanned_at: string;
  env_enabled: boolean;
  effective_enabled: boolean;
  symbols_scanned: number;
  observations_created: number;
  setup_signals: string[];
  decisions: string[];
  paper_only: boolean;
}

export interface MarketWatcherObservation {
  id: string;
  symbol: string;
  exchange: string;
  timeframe: string;
  observed_at: string;
  status: string;
  data_freshness?: string | null;
  related_strategy_id?: string | null;
  related_paper_validation_run_id?: string | null;
}

export interface PaginatedMarketWatcherObservations {
  items: MarketWatcherObservation[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarketWatcherBridgeStatus {
  env_enabled: boolean;
  auto_tick_enabled: boolean;
  effective_enabled: boolean;
  last_tick_at?: string | null;
  last_tick_status?: string | null;
  decisions_last_tick: number;
  scans_triggered_last_tick: number;
  paper_only: boolean;
  real_trading_enabled: boolean;
}

export interface MarketWatcherBridgeDecision {
  id: string;
  decision: string;
  symbol?: string | null;
  reason?: string | null;
  blockers: string[];
  triggered_scan_id?: string | null;
  created_alert_id?: string | null;
  created_at: string;
}

export interface MarketWatcherBridgeTickResult {
  ticked_at: string;
  env_enabled: boolean;
  effective_enabled: boolean;
  observations_processed: number;
  scans_triggered: number;
  decisions: string[];
  paper_only: boolean;
}

export interface PaginatedMarketWatcherBridgeHistory {
  items: MarketWatcherBridgeDecision[];
  total: number;
  limit: number;
  offset: number;
}

export interface PaperAlertSummary {
  total: number;
  unread: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
}

export interface PaginatedBacktestRuns {
  items: BacktestRun[];
  total: number;
  limit: number;
  offset: number;
}

export interface PaginatedUserStrategies {
  items: UserStrategy[];
  total: number;
  limit: number;
  offset: number;
}

export interface ManualChartLevel {
  id: string;
  symbol: string;
  exchange: string;
  timeframe?: Timeframe | null;
  level_type: ManualLevelType;
  price?: string | null;
  price_low?: string | null;
  price_high?: string | null;
  label?: string | null;
  notes?: string | null;
  enabled: boolean;
}

export interface PaginatedManualChartLevels {
  items: ManualChartLevel[];
  total: number;
  limit: number;
  offset: number;
}

export interface PositionSizingResult {
  entry_price: string;
  invalidation_level: string;
  stop_loss_distance: string;
  account_balance: string;
  max_risk_percent: string;
  maximum_acceptable_loss: string;
  notional_position_size: string;
  leverage_limit: string;
  leverage_recommendation: string;
  risk_reward_ratio?: number | null;
  required_breakeven_win_rate?: number | null;
  confidence_score: number;
  confidence_adjusted_size: string;
  worst_case_scenario: string;
  final_recommendation: PreTradeRecommendation;
  planned_loss_amount: string;
}

export interface PreTradeAnalyzeResponse {
  symbol: string;
  exchange: string;
  direction_considered?: TradeDirection | null;
  bullish_factors: string[];
  bearish_factors: string[];
  market_regime: string;
  trend_alignment_score: number;
  volume_confirmation_score: number;
  funding_risk_score: number;
  setup_confidence_score: number;
  risk_reward?: number | null;
  suggested_entry_zone?: Record<string, string> | null;
  suggested_stop_loss?: string | null;
  invalidation: string[];
  tp_levels: Record<string, string>[];
  runner_logic: string[];
  position_size?: PositionSizingResult | null;
  leverage_recommendation?: string | null;
  final_recommendation: PreTradeRecommendation;
  limitations: string[];
}

export interface RunnerAnalysis {
  early_exit_flag?: boolean | null;
  missed_profit_estimate?: string | null;
  max_favorable_excursion_after_exit?: string | null;
  max_adverse_excursion_after_exit?: string | null;
  would_runner_have_helped?: boolean | null;
  tp2_would_have_hit?: boolean | null;
  tp3_would_have_hit?: boolean | null;
  runner_invalidation_would_have_hit?: boolean | null;
  recommended_lesson?: string | null;
  confidence?: string;
  limitations?: string[];
}

export interface StopLossAnalysis {
  stop_violation_flag?: boolean | null;
  planned_loss?: string | null;
  actual_loss?: string | null;
  avoidable_loss_estimate?: string | null;
  lesson?: string | null;
  future_restriction_suggestion?: string | null;
  limitations?: string[];
}

export interface HumanVsSystemComparison {
  trade_id: string;
  symbol?: string | null;
  entry_quality_delta_pct?: number | null;
  exit_quality_delta?: string | null;
  size_discipline_delta_pct?: number | null;
  leverage_discipline_delta?: string | null;
  stop_loss_discipline_delta?: string | null;
  planned_loss_vs_actual?: string | null;
  early_exit_flag?: boolean | null;
  missed_runner?: RunnerAnalysis | null;
  emotional_mistake_classification?: string[];
  rule_violation_cost_estimate?: string | null;
  plan_adherence_score: number;
  plan_adherence: {
    entry_followed_plan: number;
    size_respected_risk: number;
    stop_loss_respected: number;
    profit_taking_followed: number;
    emotion_controlled: number;
    journal_completed: number;
  };
  system_would_have_done?: string | null;
  backtest_context?: string | null;
  stop_loss_analysis?: StopLossAnalysis | null;
  entry_delta_pct?: number | null;
  exit_delta?: string | null;
  size_delta_pct?: number | null;
  leverage_delta?: string | null;
  stop_behavior_delta?: string | null;
  missed_runner_profit_placeholder?: string | null;
  emotion_tags: string[];
  notes: string[];
  limitations?: string[];
}

export interface StrategyTestability {
  strategy_id: string;
  score: number;
  band: string;
  ready_for_backtest: boolean;
  missing_fields: { field_key: string; label: string; severity?: string }[];
  unsupported_rule_types?: string[];
  ambiguous_conditions?: string[];
  not_backtestable_reason?: string | null;
  suggested_edits?: string[];
  has_structured_rules: boolean;
  structured_rules?: StructuredRules | null;
  limitations?: string[];
}

export interface RuleCondition {
  timeframe?: string | null;
  indicator?: string | null;
  operator?: string | null;
  value?: string | number | null;
  lookback_candles?: number | null;
  confirmation_required?: boolean;
}

export interface StructuredRules {
  primary_timeframe?: string | null;
  entry_rules: {
    trigger_type: string;
    direction?: string;
    conditions?: RuleCondition[];
    notes?: string | null;
  }[];
  exit_rules: {
    rule_type: string;
    value?: string | number | null;
    r_multiple?: string | number | null;
    size_fraction?: number | null;
    conditions?: RuleCondition[];
    notes?: string | null;
  }[];
  no_trade_rules: {
    rule_type: string;
    threshold?: string | number | null;
    conditions?: RuleCondition[];
    notes?: string | null;
  }[];
}

export interface ProposedRuleUpdate {
  summary: string;
  structured_rules_patch?: StructuredRules | null;
  create_new_version?: boolean;
  attach_to_strategy?: boolean;
}

export interface LessonCandidate {
  id: string;
  organization_id: string;
  user_id: string;
  source_type: string;
  source_id?: string | null;
  related_strategy_id?: string | null;
  related_trade_id?: string | null;
  related_journal_entry_id?: string | null;
  lesson_text: string;
  mistake_type: string;
  severity: string;
  confidence?: string | null;
  status: string;
  proposed_rule_update?: ProposedRuleUpdate | null;
  accepted_rule_update?: ProposedRuleUpdate | null;
  reviewer_notes?: string | null;
  analysis_metadata?: Record<string, unknown> | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface PaginatedLessonCandidates {
  items: LessonCandidate[];
  total: number;
  limit: number;
  offset: number;
}

export interface ExchangeInstrumentSummary {
  symbol: string;
  inst_id: string;
  active?: boolean | null;
  probe_ok: boolean;
}

export interface ExchangeLeverageSummary {
  inst_id: string;
  margin_mode: string;
  leverage?: string | null;
  probe_ok: boolean;
}

export interface ExchangeDiagnosticsSummary {
  exchange_mode: string;
  execution_mode: string;
  real_trading_enabled: boolean;
  demo_active: boolean;
  provider_health?: string | null;
  worker_enabled: boolean;
  telegram_enabled: boolean;
  position_mode?: string | null;
  leverage?: ExchangeLeverageSummary | null;
  instrument?: ExchangeInstrumentSummary | null;
  venue_positions_count?: number | null;
  last_exchange_order_status?: string | null;
  last_demo_mirror_result?: string | null;
  last_demo_mirror_error_code?: string | null;
  last_demo_mirror_error_message?: string | null;
  last_cancel_status?: string | null;
  readiness: "ready" | "degraded" | "blocked";
  warnings: string[];
  generated_at: string;
}

export interface LessonSourceMetadata {
  lesson_id: string;
  mistake_type: string;
  accepted_lesson_text: string;
  rule_update_summary?: string | null;
  reviewer_notes?: string | null;
  created_at: string;
}

export interface UserStrategyVersion {
  id: string;
  strategy_id: string;
  version: number;
  card: Record<string, unknown>;
  validation_status: string;
  backtest_status: string;
  paper_validation_status: string;
  lesson_source_metadata?: LessonSourceMetadata | null;
  created_at: string;
}

export interface PaginatedUserStrategyVersions {
  items: UserStrategyVersion[];
  total: number;
  limit: number;
  offset: number;
}

export interface PaperEligibilityReport {
  strategy_id: string;
  status: string;
  paper_eligible: boolean;
  testability_score: number;
  blockers: string[];
  eligibility_reasons: string[];
  latest_backtest?: {
    trade_count: number;
    win_rate: number;
    profit_factor: number;
    expectancy: string;
    max_drawdown_pct: number;
    recommendation?: string | null;
  } | null;
  accepted_lessons: LessonCandidate[];
  unresolved_lesson_candidates: LessonCandidate[];
  paper_validation_recommendation?: string | null;
  recommendation: string;
  real_trading_enabled: boolean;
  limitations: string[];
}
