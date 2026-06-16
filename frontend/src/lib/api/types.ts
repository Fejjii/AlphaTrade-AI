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
  created_at: string;
  updated_at: string;
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

export interface HumanVsSystemComparison {
  trade_id: string;
  plan_adherence_score: number;
  plan_adherence: {
    entry_followed_plan: number;
    size_respected_risk: number;
    stop_loss_respected: number;
    profit_taking_followed: number;
    emotion_controlled: number;
    journal_completed: number;
  };
  emotion_tags: string[];
  notes: string[];
}
