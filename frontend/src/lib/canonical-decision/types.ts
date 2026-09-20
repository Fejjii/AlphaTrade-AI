/**
 * Canonical paper decision workflow contracts.
 *
 * These types describe the user-facing spine:
 * market assessment → candidate → eligibility → TradePlan → approval →
 * paper execution → outcome → learning.
 *
 * They do not create backend authority. Canonical HTTP reads and
 * POST /execution/paper-plan are bound. Legacy PVC/proposal surfaces remain
 * compatibility projections.
 */

export const DECISION_STAGES = [
  "market_assessment",
  "candidate",
  "eligibility",
  "trade_plan",
  "approval",
  "paper_execution",
  "outcome",
  "learning",
] as const;

export type DecisionStage = (typeof DECISION_STAGES)[number];

export type AuthorityKind = "canonical" | "compatibility_projection" | "unbound";

export type BindingStatus = "bound" | "partial" | "missing";

export type ActionEligibilityState = "eligible" | "blocked" | "expired";

export type SetupAssessmentState =
  | "no_setup"
  | "watch"
  | "partial_match"
  | "confirmed_setup"
  | "invalidated"
  | "expired"
  | "unknown";

export type CandidateLifecycleState =
  | "active"
  | "plan_created"
  | "rejected"
  | "skipped"
  | "expired"
  | "invalidated"
  | "unknown";

export type EligibilityReasonCode =
  | "eligible"
  | "blocked_kill_switch"
  | "blocked_daily_loss"
  | "blocked_weekly_loss"
  | "blocked_cooldown"
  | "blocked_exposure"
  | "blocked_portfolio_conflict"
  | "blocked_account_state"
  | "blocked_venue_state"
  | "blocked_data_quality"
  | "blocked_basis"
  | "blocked_candidate_ttl"
  | "blocked_candidate_state"
  | "blocked_configuration"
  | "blocked_setup_not_confirmed"
  | "blocked_human_approval_required"
  | "blocked_loss_acceptance"
  | "blocked_risk_engine"
  | "expired";

export type MarketQualityGrade = "tradeable" | "watch" | "poor" | "unknown";

export type CanonicalFreshnessPillState =
  | "live"
  | "delayed"
  | "stale"
  | "fallback"
  | "unavailable"
  | "replay";

export interface CurrentPriceHonesty {
  usableAsCurrentMarketPrice: boolean;
  presentation: string;
  price: string | null;
  sourceTime: string | null;
  venueTradeId: string | null;
  isLive: boolean;
  isMock: boolean;
  fallbackUsed: false;
  freshnessState: CanonicalFreshnessPillState;
  freshnessPolicyVersion: string;
  ageSeconds: string | null;
}

export type PaperExecutionStatus =
  | "not_started"
  | "blocked"
  | "awaiting_submit"
  | "submitting"
  | "pending"
  | "filled"
  | "cancelled"
  | "rejected"
  | "unknown";

export type DecisionCaseKind =
  | "canonical_candidate"
  | "compatibility_candidate"
  | "legacy_proposal"
  | "linked_outcome";

export interface EvidenceFact {
  label: string;
  detail: string;
  freshness?: string | null;
  isLive?: boolean | null;
  fallbackUsed?: boolean | null;
  stale?: boolean | null;
  freshnessState?: CanonicalFreshnessPillState | null;
}

export interface MarketQualityView {
  authority: AuthorityKind;
  grade: MarketQualityGrade;
  setupState: SetupAssessmentState;
  dataQuality: string | null;
  confidence: number | null;
  confidencePenaltyApplied: boolean;
  symbol: string | null;
  timeframe: string | null;
  direction: string | null;
  evidence: EvidenceFact[];
  summary: string;
  /**
   * Canonical current perpetual mark, or null when this view must not present a
   * market price (compatibility snapshots, candidates, proposals).
   */
  currentPrice: CurrentPriceHonesty | null;
  /** Market quality never implies permission to act. */
  doesNotGrantEligibility: true;
}

export interface ActionEligibilityView {
  authority: AuthorityKind;
  state: ActionEligibilityState;
  paperActionable: boolean;
  liveExecutable: false;
  reasonCodes: EligibilityReasonCode[];
  explanations: EligibilityExplanation[];
  checkedAt: string | null;
  validUntil: string | null;
  killSwitchActive: boolean;
  humanApprovalSatisfied: boolean;
}

export interface EligibilityExplanation {
  code: EligibilityReasonCode;
  title: string;
  detail: string;
  domain: "action" | "configuration" | "approval";
  blocking: boolean;
}

export interface CandidateWorkspaceView {
  authority: AuthorityKind;
  caseId: string;
  sourceId: string;
  sourceKind: DecisionCaseKind;
  lifecycleState: CandidateLifecycleState;
  symbol: string | null;
  timeframe: string | null;
  direction: string | null;
  setupLabel: string | null;
  thesis: string | null;
  entryCriteria: string | null;
  invalidation: string | null;
  confidence: number | null;
  evidence: EvidenceFact[];
  strategyId: string | null;
  createdAt: string | null;
  legacyHref: string | null;
  marketQuality: MarketQualityView;
  eligibility: ActionEligibilityView;
}

export interface TradePlanLevel {
  label: string;
  price: string | null;
  fraction?: string | null;
}

export interface TradePlanViewModel {
  authority: AuthorityKind;
  proposalId: string;
  revisionId: string | null;
  planId: string | null;
  candidateId: string | null;
  symbol: string;
  direction: string;
  timeframe: string;
  strategyId: string;
  entry: string | null;
  stop: string | null;
  targets: TradePlanLevel[];
  size: string | null;
  leverage: string | null;
  riskBudget: string | null;
  maximumLoss: string | null;
  rationale: string | null;
  contentHash: string | null;
  correlationId: string | null;
  strategyVersionId: string | null;
  setupDefinitionId: string | null;
  evidenceIds: string[];
  validFrom: string | null;
  validUntil: string | null;
  createdAt: string | null;
  riskAction: "allow" | "warn" | "block" | null;
  riskSummary: string | null;
  approvalRequired: boolean;
  lineage: TradePlanLineageItem[];
}

export interface TradePlanLineageItem {
  label: string;
  value: string;
  href?: string | null;
}

export interface PaperApprovalView {
  approvalId: string;
  proposalId: string;
  status: string;
  createdAt: string;
  decidedAt: string | null;
  reason: string | null;
  humanApprovalRequired: true;
  aiCannotBypass: true;
  recordsAuthorizationOnly: true;
  doesNotPlaceOrder: true;
}

export interface PaperExecutionView {
  orderId: string | null;
  receiptId: string | null;
  proposalId: string | null;
  approvalId: string | null;
  status: PaperExecutionStatus;
  symbol: string | null;
  side: string | null;
  size: string | null;
  mode: "paper";
  liveExecutionAvailable: false;
  createdAt: string | null;
  blockReason: string | null;
  authority: AuthorityKind;
}

export interface OutcomeView {
  journalId: string | null;
  positionId: string | null;
  proposalId: string | null;
  symbol: string | null;
  result: string | null;
  pnl: string | null;
  lessons: string | null;
  href: string | null;
}

export interface LearningView {
  lessonId: string | null;
  status: string | null;
  lessonText: string | null;
  mistakeType: string | null;
  href: string | null;
}

export interface DecisionCase {
  id: string;
  kind: DecisionCaseKind;
  stage: DecisionStage;
  symbol: string;
  direction: string | null;
  timeframe: string | null;
  title: string;
  summary: string;
  href: string;
  createdAt: string | null;
  candidate: CandidateWorkspaceView | null;
  tradePlan: TradePlanViewModel | null;
  approval: PaperApprovalView | null;
  execution: PaperExecutionView | null;
  outcome: OutcomeView | null;
  learning: LearningView | null;
}

export interface DecisionQueueSnapshot {
  cases: DecisionCase[];
  stageCounts: Record<DecisionStage, number>;
  missingBindings: string[];
}

export interface CanonicalCandidateContract {
  schema_version: "Candidate/v1";
  candidate_id: string;
  organization_id: string;
  user_id: string;
  account_id: string;
  revision: number;
  state: CandidateLifecycleState;
  assessment_id: string;
  strategy_version_id: string;
  compiled_setup_id: string;
  direction: string;
  venue: string;
  instrument: string;
  timeframe: string;
  evidence_window_hash: string;
  confidence: number | null;
  correlation_id: string;
  content_hash: string;
  created_at: string;
}

export interface CanonicalActionEligibilityContract {
  schema_version: "ActionEligibility/v1";
  eligibility_id: string;
  organization_id: string;
  user_id: string;
  account_id: string;
  candidate_id: string;
  candidate_revision: number;
  assessment_id: string;
  risk_snapshot_id: string;
  venue_state_id: string;
  state: ActionEligibilityState;
  reason_codes: EligibilityReasonCode[];
  live_executable: false;
  paper_actionable: boolean;
  checked_at: string;
  valid_until: string;
  correlation_id: string;
  content_hash: string;
}

export interface CanonicalExecutionReceiptContract {
  schema_version: "ExecutionReceipt/v1";
  receipt_id: string;
  plan_revision_id: string;
  authorization_id: string;
  command_id: string;
  state: PaperExecutionStatus;
  mode: "PAPER";
  live_execution: false;
  correlation_id: string;
  created_at: string;
}

export interface CanonicalTradePlanRevisionContract {
  schema_version: "CanonicalTradePlanContentV1";
  plan_id: string;
  revision_id: string;
  organization_id: string;
  user_id: string;
  account_id: string;
  candidate_id: string;
  strategy_version_id: string;
  setup_definition_id: string;
  side: "BUY" | "SELL";
  timeframe: string;
  execution_instrument: string;
  evidence_instrument: string;
  quantity: { value: string; unit: string };
  quantity_unit: string;
  order_type: string;
  limit_price: { value: string; unit: string } | null;
  risk_and_exits: {
    stop: { value: string; unit: string };
    targets: Array<{
      order: number;
      price: { value: string; unit: string };
      quantity_fraction: string;
    }>;
    risk_budget: { value: string; unit: string };
    maximum_loss: { value: string; unit: string };
    leverage: string;
  };
  content_hash: string;
  correlation_id: string;
  created_at: string;
  valid_from: string;
  valid_until: string;
  evidence_ids: string[];
}
