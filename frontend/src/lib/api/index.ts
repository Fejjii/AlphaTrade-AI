import { apiFetch } from "@/lib/api/client";
import type {
  AgentMessageResponse,
  ApprovalRequest,
  AuditRecord,
  AuthResponse,
  HealthResponse,
  IngestDocumentResponse,
  DisciplineScoreResult,
  DashboardSummary,
  JournalEntry,
  RiskBehaviorAnalytics,
  SetupAnalyticsResponse,
  TradeReviewAnalytics,
  MeResponse,
  MessageResponse,
  OrganizationInvitation,
  InvitationListResponse,
  PaginatedApprovalRequests,
  PaginatedAuditRecords,
  PaginatedJournalEntries,
  PaginatedPositions,
  PaginatedTradeProposals,
  PaginatedUsageEvents,
  PaperOrder,
  ProposalWorkflowView,
  ApprovalWorkflowView,
  Position,
  ProviderStatusResponse,
  RagSearchResponse,
  ReadinessResponse,
  TokenPair,
  TradeProposal,
  UsageSummary,
  UsageFeatureBreakdown,
  SubscriptionPlan,
  BillingStatus,
  BillingCustomer,
  CheckoutResponse,
  PortalResponse,
  UsageExportResponse,
  UsageProviderBreakdown,
  QuotaStatus,
  OrganizationQuotaConfig,
  MembershipRole,
  MarketAnalyzeResponse,
  ManualChartLevel,
  PaginatedManualChartLevels,
  PaginatedUserStrategies,
  PaginatedUserStrategyVersions,
  PaperEligibilityReport,
  PreTradeAnalyzeResponse,
  PositionSizingResult,
  HumanVsSystemComparison,
  UserStrategy,
  UserRiskSettings,
  UserRiskSettingsUpdate,
  BacktestRun,
  PaginatedBacktestRuns,
  PaginatedBacktestTrades,
  PaperValidationMetrics,
  PaperValidationRun,
  PaperValidationSummary,
  PaperSchedulerStatus,
  PaperSchedulerTickResult,
  PaperRuntimeHistoryRecord,
  PaperAlert,
  PaperAlertSummary,
  SetupAlertReviewItem,
  SetupAlertReviewSummary,
  SetupAlertDraftCreateResult,
  PaperValidationDraftChecklist,
  PaperValidationDraftItem,
  PaperValidationDraftPrepStatus,
  PaperValidationDraftSummary,
  PaperValidationCandidateItem,
  PaperValidationCandidateQueueResult,
  PaperValidationCandidateSummary,
  PaperValidationRunPlanCreateResult,
  PaperValidationRunPlanItem,
  PaperValidationRunPlanSummary,
  PaperValidationRunSessionItem,
  PaperValidationRunSessionStartResult,
  AlertDeliveryStatusResponse,
  NotificationPreferences,
  NotificationTestResult,
  MarketWatcherStatus,
  MarketWatcherSummary,
  MarketWatcherScanRequest,
  MarketWatcherScanResult,
  PaginatedMarketWatcherRecentScans,
  MarketWatcherBridgeStatus,
  MarketWatcherBridgeTickResult,
  PaginatedMarketWatcherBridgeHistory,
  PaginatedMarketWatcherObservations,
  PaperScanResult,
  PaperSignalResult,
  PaperTickResult,
  PaperTradeRecord,
  StrategyTestability,
  StructuredRules,
  LessonCandidate,
  PaginatedLessonCandidates,
  MarketSnapshotResponse,
  OHLCVResponse,
  TickerResponse,
  WatchlistItem,
  ExchangeDiagnosticsSummary,
  AlertDeliveryPreviewResponse,
  AlertRoutingSummary,
  TelegramAlertDeliveryResponse,
  TelegramTestAlertResponse,
} from "@/lib/api/types";

export const api = {
  auth: {
    register: (body: { email: string; password: string; organization_name: string }) =>
      apiFetch<AuthResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
        auth: false,
      }),
    login: (body: { email: string; password: string }) =>
      apiFetch<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
        auth: false,
      }),
    refresh: (refresh_token: string) =>
      apiFetch<TokenPair>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token }),
        auth: false,
      }),
    logout: (refresh_token?: string) =>
      apiFetch<{ message: string }>("/auth/logout", {
        method: "POST",
        body: JSON.stringify(refresh_token ? { refresh_token } : {}),
        auth: true,
      }),
    me: () => apiFetch<MeResponse>("/auth/me", { auth: true }),
    requestVerifyEmail: (body?: { email?: string }) =>
      apiFetch<MessageResponse>("/auth/verify-email/request", {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    confirmVerifyEmail: (token: string) =>
      apiFetch<MessageResponse>("/auth/verify-email/confirm", {
        method: "POST",
        body: JSON.stringify({ token }),
        auth: false,
      }),
    requestPasswordReset: (email: string) =>
      apiFetch<MessageResponse>("/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ email }),
        auth: false,
      }),
    confirmPasswordReset: (token: string, new_password: string) =>
      apiFetch<MessageResponse>("/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password }),
        auth: false,
      }),
  },
  organizations: {
    listInvitations: () => apiFetch<InvitationListResponse>("/organizations/invitations"),
    createInvitation: (body: { email: string; role: MembershipRole }) =>
      apiFetch<OrganizationInvitation>("/organizations/invitations", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    acceptInvitation: (id: string, token: string) =>
      apiFetch<OrganizationInvitation>(`/organizations/invitations/${id}/accept`, {
        method: "POST",
        body: JSON.stringify({ token }),
      }),
    revokeInvitation: (id: string) =>
      apiFetch<OrganizationInvitation>(`/organizations/invitations/${id}/revoke`, {
        method: "POST",
      }),
  },
  health: {
    get: () => apiFetch<HealthResponse>("/health", { auth: false }),
    ready: () => apiFetch<ReadinessResponse>("/health/ready", { auth: false }),
  },
  providers: {
    status: () => apiFetch<ProviderStatusResponse>("/providers/status", { auth: false }),
  },
  exchange: {
    diagnosticsSummary: () =>
      apiFetch<ExchangeDiagnosticsSummary>("/exchange/diagnostics/summary", { auth: true }),
  },
  chat: {
    message: (body: { message: string; conversation_id?: string; symbol?: string; timeframe?: string }) =>
      apiFetch<AgentMessageResponse>("/chat/message", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
  watchlist: {
    list: (params?: { limit?: number; offset?: number }) =>
      apiFetch<WatchlistItem[]>("/market/watchlist", { query: params }),
    create: (body: {
      symbol: string;
      exchange: string;
      timeframes: string[];
      strategy_ids: string[];
      enabled?: boolean;
      organization_id?: string;
      user_id?: string;
    }) =>
      apiFetch<WatchlistItem>("/market/watchlist", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    update: (
      id: string,
      body: { timeframes?: string[]; strategy_ids?: string[]; enabled?: boolean },
    ) =>
      apiFetch<WatchlistItem>(`/market/watchlist/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    delete: (id: string) =>
      apiFetch<void>(`/market/watchlist/${id}`, {
        method: "DELETE",
      }),
  },
  proposals: {
    list: (params?: { limit?: number; offset?: number; status?: string }) =>
      apiFetch<PaginatedTradeProposals>("/proposals", { query: params }),
    get: (id: string) => apiFetch<TradeProposal>(`/proposals/${id}`),
    workflow: (id: string) => apiFetch<ProposalWorkflowView>(`/proposals/${id}/workflow`),
    lossAcceptance: (id: string, body: { planned_loss_amount: string; accepted: boolean }) =>
      apiFetch<TradeProposal>(`/proposals/${id}/loss-acceptance`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
  },
  approvals: {
    list: (params?: { limit?: number; offset?: number; status?: string }) =>
      apiFetch<PaginatedApprovalRequests>("/approvals", { query: params }),
    get: (id: string) => apiFetch<ApprovalRequest>(`/approvals/${id}`),
    workflow: (id: string) => apiFetch<ApprovalWorkflowView>(`/approvals/${id}/workflow`),
    approve: (id: string, reason?: string) =>
      apiFetch<ApprovalRequest>(`/approvals/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    reject: (id: string, reason?: string) =>
      apiFetch<ApprovalRequest>(`/approvals/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    modify: (id: string, reason?: string, modified_fields?: Record<string, string>) =>
      apiFetch<ApprovalRequest>(`/approvals/${id}/modify`, {
        method: "POST",
        body: JSON.stringify({ reason, modified_fields }),
      }),
    needsMoreAnalysis: (id: string, reason?: string) =>
      apiFetch<ApprovalRequest>(`/approvals/${id}/needs-more-analysis`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
  },
  execution: {
    paperOrder: (body: {
      proposal_id: string;
      approval_id?: string;
      idempotency_key?: string;
      symbol?: string;
      side?: string;
      type?: string;
      size?: string;
    }) =>
      apiFetch<PaperOrder>("/execution/paper", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
  positions: {
    list: (params?: { limit?: number; offset?: number; status?: string }) =>
      apiFetch<PaginatedPositions>("/positions", { query: params }),
    get: (id: string) => apiFetch<Position>(`/positions/${id}`),
    closePaper: (id: string, body: { exit_price: string; reason?: string }) =>
      apiFetch<Position>(`/positions/${id}/close-paper`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
  journal: {
    list: (params?: { limit?: number; offset?: number }) =>
      apiFetch<PaginatedJournalEntries>("/journal/entries", { query: params }),
    prefill: (params: { linked_proposal_id?: string; linked_position_id?: string }) =>
      apiFetch<{
        symbol: string;
        timeframe: string;
        direction: string;
        strategy_id?: string | null;
        entry_rationale: string;
        linked_proposal_id?: string | null;
        linked_position_id?: string | null;
        tags: string[];
      }>("/journal/prefill", { query: params }),
    create: (body: {
      symbol: string;
      timeframe: string;
      direction: string;
      entry_rationale: string;
      lessons?: string;
      improvement_rule?: string;
      emotions?: string[];
      mistakes?: string[];
      strategy_id?: string;
      linked_proposal_id?: string;
      linked_position_id?: string;
      organization_id?: string;
      user_id?: string;
    }) =>
      apiFetch<JournalEntry>("/journal/entries", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    delete: (id: string) =>
      apiFetch<void>(`/journal/entries/${id}`, { method: "DELETE" }),
  },
  analytics: {
    setups: () => apiFetch<SetupAnalyticsResponse>("/analytics/setups"),
    tradeReview: () => apiFetch<TradeReviewAnalytics>("/analytics/trade-review"),
    discipline: () => apiFetch<DisciplineScoreResult>("/analytics/discipline"),
    riskBehavior: () => apiFetch<RiskBehaviorAnalytics>("/analytics/risk-behavior"),
  },
  dashboard: {
    summary: () => apiFetch<DashboardSummary>("/dashboard/summary"),
  },
  knowledge: {
    ingest: (body: {
      title: string;
      text: string;
      source_type: string;
      strategy_tag?: string;
      symbol_tag?: string;
    }) =>
      apiFetch<IngestDocumentResponse>("/knowledge/ingest", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    search: (body: {
      query: string;
      top_k?: number;
      source_types?: string[];
    }) =>
      apiFetch<RagSearchResponse>("/knowledge/search", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
  billing: {
    plans: () => apiFetch<SubscriptionPlan[]>("/billing/plans"),
    status: () => apiFetch<BillingStatus>("/billing/status"),
    createCustomer: (body?: { billing_email?: string }) =>
      apiFetch<BillingCustomer>("/billing/customer", {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    checkout: (planId: string) =>
      apiFetch<CheckoutResponse>("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_id: planId }),
      }),
    portal: () =>
      apiFetch<PortalResponse>("/billing/portal", {
        method: "POST",
      }),
    exportUsage: () =>
      apiFetch<UsageExportResponse>("/billing/usage/export", {
        method: "POST",
        body: JSON.stringify({}),
      }),
  },
  usage: {
    summary: () => apiFetch<UsageSummary>("/usage/summary"),
    events: (params?: { limit?: number; offset?: number }) =>
      apiFetch<PaginatedUsageEvents>("/usage/events", { query: params }),
    byFeature: () => apiFetch<UsageFeatureBreakdown[]>("/usage/by-feature"),
    byProvider: () => apiFetch<UsageProviderBreakdown[]>("/usage/by-provider"),
    quota: () => apiFetch<QuotaStatus>("/usage/quota"),
    updateQuota: (body: Partial<OrganizationQuotaConfig>) =>
      apiFetch<QuotaStatus>("/usage/quota", {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
  },
  audit: {
    events: (params?: { limit?: number; offset?: number; event_type?: string }) =>
      apiFetch<PaginatedAuditRecords>("/audit/events", { query: params }),
  },
  alerts: {
    list: (params?: {
      alert_type?: string;
      severity?: string;
      unread_only?: boolean;
      limit?: number;
    }) =>
      apiFetch<{ items: PaperAlert[]; total: number }>("/alerts", { query: params, auth: true }),
    summary: () => apiFetch<PaperAlertSummary>("/alerts/summary", { auth: true }),
    setupReview: (params?: {
      status?: string;
      condition?: string;
      symbol?: string;
      timeframe?: string;
      direction?: string;
      min_confidence?: number;
      limit?: number;
      offset?: number;
    }) =>
      apiFetch<{ items: SetupAlertReviewItem[]; total: number; limit: number; offset: number }>(
        "/alerts/setup-review",
        { query: params, auth: true },
      ),
    setupReviewSummary: () =>
      apiFetch<SetupAlertReviewSummary>("/alerts/setup-review/summary", { auth: true }),
    updateSetupReview: (
      id: string,
      body: { review_status: string; review_notes?: string | null },
    ) =>
      apiFetch<SetupAlertReviewItem>(`/alerts/setup-review/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    createSetupDraft: (
      id: string,
      body: { confirm: string; notes?: string | null; risk_mode?: string },
    ) =>
      apiFetch<SetupAlertDraftCreateResult>(`/alerts/setup-review/${id}/draft`, {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    routingSummary: () =>
      apiFetch<AlertRoutingSummary>("/alerts/routing/summary", { auth: true }),
    deliveryStatus: () =>
      apiFetch<AlertDeliveryStatusResponse>("/alerts/delivery-status", { auth: true }),
    markRead: (id: string) =>
      apiFetch<PaperAlert>(`/alerts/${id}/read`, { method: "PATCH", auth: true }),
    markAllRead: () =>
      apiFetch<{ marked_read: number }>("/alerts/read-all", { method: "PATCH", auth: true }),
    deliver: (id: string) =>
      apiFetch<{ alert: PaperAlert; delivered: boolean; message: string }>(
        `/alerts/${id}/deliver`,
        { method: "POST", auth: true },
      ),
    deliverPending: () =>
      apiFetch<{ processed: number; delivered: number; failed: number }>(
        "/alerts/deliver-pending",
        { method: "POST", auth: true },
      ),
    testTelegram: (body: { confirm: string; message?: string }) =>
      apiFetch<TelegramTestAlertResponse>("/alerts/test-telegram", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    deliverTelegram: (id: string, body: { confirm: string }) =>
      apiFetch<TelegramAlertDeliveryResponse>(`/alerts/${id}/deliver-telegram`, {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    previewDelivery: (body: {
      channel?: "telegram";
      limit?: number;
      severity_min?: string;
    }) =>
      apiFetch<AlertDeliveryPreviewResponse>("/alerts/delivery/preview", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
  },
  notifications: {
    preferences: () =>
      apiFetch<NotificationPreferences>("/notifications/preferences", { auth: true }),
    updatePreferences: (body: Partial<NotificationPreferences>) =>
      apiFetch<NotificationPreferences>("/notifications/preferences", {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    resetPreferences: () =>
      apiFetch<NotificationPreferences>("/notifications/preferences/reset-defaults", {
        method: "POST",
        auth: true,
      }),
    sendTest: () =>
      apiFetch<NotificationTestResult>("/notifications/test", { method: "POST", auth: true }),
  },
  marketWatcher: {
    status: () => apiFetch<MarketWatcherStatus>("/market-watcher/status", { auth: true }),
    summary: () => apiFetch<MarketWatcherSummary>("/market-watcher/summary", { auth: true }),
    scan: (body: MarketWatcherScanRequest) =>
      apiFetch<MarketWatcherScanResult>("/market-watcher/scan", {
        method: "POST",
        auth: true,
        body: JSON.stringify(body),
      }),
    recentScans: (limit = 10) =>
      apiFetch<PaginatedMarketWatcherRecentScans>("/market-watcher/scans/recent", {
        auth: true,
        query: { limit },
      }),
    observations: (params?: { symbol?: string; limit?: number; offset?: number }) =>
      apiFetch<PaginatedMarketWatcherObservations>("/market-watcher/observations", {
        auth: true,
        query: params,
      }),
    bridgeStatus: () =>
      apiFetch<MarketWatcherBridgeStatus>("/market-watcher/bridge/status", { auth: true }),
    bridgeTick: () =>
      apiFetch<MarketWatcherBridgeTickResult>("/market-watcher/bridge/tick", {
        method: "POST",
        auth: true,
      }),
    bridgeHistory: (params?: { limit?: number; offset?: number }) =>
      apiFetch<PaginatedMarketWatcherBridgeHistory>("/market-watcher/bridge/history", {
        auth: true,
        query: params,
      }),
  },
  market: {
    ticker: (params?: { symbol?: string; exchange?: string }) =>
      apiFetch<TickerResponse>("/market/ticker", { query: params }),
    ohlcv: (params?: { symbol?: string; exchange?: string; timeframe?: string; limit?: number }) =>
      apiFetch<OHLCVResponse>("/market/ohlcv", { query: params }),
    snapshot: (params?: { symbol?: string; exchange?: string; timeframe?: string }) =>
      apiFetch<MarketSnapshotResponse>("/market/snapshots", { query: params }),
    analyze: (body: {
      symbol: string;
      exchange?: string;
      timeframe?: string;
      strategy_ids?: string[];
    }) =>
      apiFetch<MarketAnalyzeResponse>("/market/analyze", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    snapshots: (params?: { symbol?: string; exchange?: string; timeframe?: string }) =>
      apiFetch<MarketSnapshotResponse>("/market/snapshots", { query: params }),
  },
  strategies: {
    list: (params?: { limit?: number; offset?: number }) =>
      apiFetch<PaginatedUserStrategies>("/strategies", { query: params, auth: true }),
    get: (id: string) => apiFetch<UserStrategy>(`/strategies/${id}`, { auth: true }),
    create: (body: {
      name: string;
      setup_type: string;
      card: Record<string, unknown>;
      notes?: string;
    }) =>
      apiFetch<UserStrategy>("/strategies", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    modules: () => apiFetch<string[]>("/strategies/modules", { auth: false }),
    update: (id: string, body: { name?: string; card?: Record<string, unknown> }) =>
      apiFetch<UserStrategy>(`/strategies/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    createVersion: (id: string, body: { card: Record<string, unknown>; validation_status?: string }) =>
      apiFetch<{ id: string; version: number }>(`/strategies/${id}/versions`, {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    requestBacktest: (id: string, body?: Record<string, unknown>) =>
      apiFetch<BacktestRun>(`/strategies/${id}/backtests`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
        auth: true,
      }),
    listBacktests: (id: string) =>
      apiFetch<PaginatedBacktestRuns>(`/strategies/${id}/backtests`, { auth: true }),
    listBacktestTrades: (runId: string) =>
      apiFetch<PaginatedBacktestTrades>(`/backtests/${runId}/trades`, { auth: true }),
    listVersions: (id: string) =>
      apiFetch<PaginatedUserStrategyVersions>(`/strategies/${id}/versions`, { auth: true }),
    paperEligibility: (id: string) =>
      apiFetch<PaperEligibilityReport>(`/strategies/${id}/paper-eligibility`, { auth: true }),
    startPaperValidation: (id: string, body?: Record<string, unknown>) =>
      apiFetch<{ id: string; status: string }>(`/strategies/${id}/paper-validation/start`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
        auth: true,
      }),
    paperValidation: (id: string) =>
      apiFetch<PaperValidationSummary>(`/strategies/${id}/paper-validation`, { auth: true }),
    scanPaperValidation: (runId: string) =>
      apiFetch<PaperScanResult>(`/paper-validation/${runId}/scan`, {
        method: "POST",
        auth: true,
      }),
    tickPaperValidation: (runId: string) =>
      apiFetch<PaperTickResult>(`/paper-validation/${runId}/tick`, {
        method: "POST",
        auth: true,
      }),
    stopPaperValidation: (runId: string) =>
      apiFetch<PaperValidationRun>(`/paper-validation/${runId}/stop`, {
        method: "POST",
        auth: true,
      }),
    paperValidationSignals: (runId: string) =>
      apiFetch<{ items: PaperSignalResult[]; total: number }>(
        `/paper-validation/${runId}/signals`,
        { auth: true },
      ),
    paperValidationTrades: (runId: string) =>
      apiFetch<{ items: PaperTradeRecord[]; total: number }>(
        `/paper-validation/${runId}/trades`,
        { auth: true },
      ),
    paperValidationMetrics: (runId: string) =>
      apiFetch<PaperValidationMetrics>(`/paper-validation/${runId}/metrics`, { auth: true }),
    schedulerStatus: () =>
      apiFetch<PaperSchedulerStatus>("/paper-validation/scheduler/status", { auth: true }),
    schedulerTick: () =>
      apiFetch<PaperSchedulerTickResult>("/paper-validation/scheduler/tick", {
        method: "POST",
        auth: true,
      }),
    schedulerHistory: (params?: { run_id?: string; limit?: number }) =>
      apiFetch<{ items: PaperRuntimeHistoryRecord[]; total: number }>(
        "/paper-validation/scheduler/history",
        { query: params, auth: true },
      ),
    drafts: (params?: { limit?: number; offset?: number }) =>
      apiFetch<{ items: PaperValidationDraftItem[]; total: number; limit: number; offset: number }>(
        "/paper-validation/drafts",
        { query: params, auth: true },
      ),
    getDraft: (id: string) =>
      apiFetch<PaperValidationDraftItem>(`/paper-validation/drafts/${id}`, { auth: true }),
    updateDraftPrep: (
      id: string,
      body: {
        prep_status?: PaperValidationDraftPrepStatus;
        thesis?: string | null;
        entry_criteria?: string | null;
        invalidation_criteria?: string | null;
        risk_notes?: string | null;
        checklist?: Partial<PaperValidationDraftChecklist>;
      },
    ) =>
      apiFetch<PaperValidationDraftItem>(`/paper-validation/drafts/${id}/prep`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    draftSummary: () =>
      apiFetch<PaperValidationDraftSummary>("/paper-validation/drafts/summary", { auth: true }),
    queueDraft: (id: string, body: { confirm: string }) =>
      apiFetch<PaperValidationCandidateQueueResult>(`/paper-validation/drafts/${id}/queue`, {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    candidates: (params?: { limit?: number; offset?: number }) =>
      apiFetch<{ items: PaperValidationCandidateItem[]; total: number; limit: number; offset: number }>(
        "/paper-validation/candidates",
        { query: params, auth: true },
      ),
    getCandidate: (id: string) =>
      apiFetch<PaperValidationCandidateItem>(`/paper-validation/candidates/${id}`, { auth: true }),
    updateCandidateStatus: (id: string, body: { candidate_status: string }) =>
      apiFetch<PaperValidationCandidateItem>(`/paper-validation/candidates/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    candidateSummary: () =>
      apiFetch<PaperValidationCandidateSummary>("/paper-validation/candidates/summary", {
        auth: true,
      }),
    createRunPlan: (
      candidateId: string,
      body: {
        confirm: string;
        validation_window: string;
        observation_timeframe: string;
        max_duration_minutes: number;
        planned_entry_rule: string;
        planned_invalidation_rule: string;
        planned_success_criteria: string;
        planned_failure_criteria: string;
      },
    ) =>
      apiFetch<PaperValidationRunPlanCreateResult>(
        `/paper-validation/candidates/${candidateId}/plan`,
        {
          method: "POST",
          body: JSON.stringify(body),
          auth: true,
        },
      ),
    runPlans: (params?: { limit?: number; offset?: number }) =>
      apiFetch<{ items: PaperValidationRunPlanItem[]; total: number; limit: number; offset: number }>(
        "/paper-validation/run-plans",
        { query: params, auth: true },
      ),
    getRunPlan: (id: string) =>
      apiFetch<PaperValidationRunPlanItem>(`/paper-validation/run-plans/${id}`, { auth: true }),
    updateRunPlanStatus: (id: string, body: { plan_status: string }) =>
      apiFetch<PaperValidationRunPlanItem>(`/paper-validation/run-plans/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    runPlanSummary: () =>
      apiFetch<PaperValidationRunPlanSummary>("/paper-validation/run-plans/summary", {
        auth: true,
      }),
    startRunSession: (planId: string, body: { confirm: string; notes?: string | null }) =>
      apiFetch<PaperValidationRunSessionStartResult>(
        `/paper-validation/run-plans/${planId}/start`,
        {
          method: "POST",
          body: JSON.stringify(body),
          auth: true,
        },
      ),
    runSessions: (params?: { limit?: number; offset?: number }) =>
      apiFetch<{
        items: PaperValidationRunSessionItem[];
        total: number;
        limit: number;
        offset: number;
      }>("/paper-validation/run-sessions", { query: params, auth: true }),
    getRunSession: (id: string) =>
      apiFetch<PaperValidationRunSessionItem>(`/paper-validation/run-sessions/${id}`, {
        auth: true,
      }),
    updateRunSessionStatus: (id: string, body: { session_status: string }) =>
      apiFetch<PaperValidationRunSessionItem>(`/paper-validation/run-sessions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    testability: (id: string) =>
      apiFetch<StrategyTestability>(`/strategies/${id}/testability`, { auth: true }),
    patchStructuredRules: (id: string, body: Partial<StructuredRules>) =>
      apiFetch<StructuredRules>(`/strategies/${id}/structured-rules`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    validateStructuredRules: (id: string, body: StructuredRules) =>
      apiFetch<{ valid: boolean; errors: string[]; warnings: string[] }>(
        `/strategies/${id}/structured-rules/validate`,
        { method: "POST", body: JSON.stringify(body), auth: true },
      ),
    structureFromText: (id: string, text: string) =>
      apiFetch<{ draft?: StructuredRules; validation: { valid: boolean } }>(
        `/strategies/${id}/structure-from-text`,
        { method: "POST", body: JSON.stringify({ text }), auth: true },
      ),
  },
  manualLevels: {
    list: (params?: { symbol?: string; exchange?: string }) =>
      apiFetch<PaginatedManualChartLevels>("/manual-levels", { query: params, auth: true }),
    create: (body: Record<string, unknown>) =>
      apiFetch<ManualChartLevel>("/manual-levels", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    update: (id: string, body: Record<string, unknown>) =>
      apiFetch<ManualChartLevel>(`/manual-levels/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    delete: (id: string) =>
      apiFetch<void>(`/manual-levels/${id}`, { method: "DELETE", auth: true }),
  },
  pretrade: {
    analyze: (body: Record<string, unknown>) =>
      apiFetch<PreTradeAnalyzeResponse>("/pretrade/analyze", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
  },
  risk: {
    settings: () => apiFetch<UserRiskSettings>("/risk/settings", { auth: true }),
    updateSettings: (body: UserRiskSettingsUpdate) =>
      apiFetch<UserRiskSettings>("/risk/settings", {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    resetSettings: () =>
      apiFetch<UserRiskSettings>("/risk/settings/reset-defaults", {
        method: "POST",
        auth: true,
      }),
    size: (body: Record<string, unknown>) =>
      apiFetch<PositionSizingResult>("/risk/size", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    lossAcceptance: (body: { planned_loss_amount: string; accepted: boolean }) =>
      apiFetch<{ can_execute_paper: boolean; recommendation: string }>("/risk/loss-acceptance", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
  },
  humanVsSystem: {
    compare: (tradeId: string) =>
      apiFetch<HumanVsSystemComparison>(`/human-vs-system/${tradeId}`, { auth: true }),
    analyze: (tradeId: string) =>
      apiFetch<HumanVsSystemComparison>(`/human-vs-system/${tradeId}/analyze`, { auth: true }),
  },
  journalDiscipline: {
    analyze: (journalId: string) =>
      apiFetch<{
        journal_entry_id: string;
        comparison: HumanVsSystemComparison;
        lessons_generated: string[];
        lesson_candidate_ids: string[];
      }>(`/journal/entries/${journalId}/discipline-analysis`, { auth: true }),
  },
  lessons: {
    listCandidates: (params?: { status?: string; mistake_type?: string }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set("status", params.status);
      if (params?.mistake_type) q.set("mistake_type", params.mistake_type);
      const suffix = q.toString() ? `?${q}` : "";
      return apiFetch<PaginatedLessonCandidates>(`/lessons/candidates${suffix}`, { auth: true });
    },
    getCandidate: (id: string) =>
      apiFetch<LessonCandidate>(`/lessons/candidates/${id}`, { auth: true }),
    createCandidate: (body: Record<string, unknown>) =>
      apiFetch<LessonCandidate>("/lessons/candidates", {
        method: "POST",
        body: JSON.stringify(body),
        auth: true,
      }),
    accept: (id: string, body: Record<string, unknown>) =>
      apiFetch<LessonCandidate>(`/lessons/candidates/${id}/accept`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    reject: (id: string, body: Record<string, unknown>) =>
      apiFetch<LessonCandidate>(`/lessons/candidates/${id}/reject`, {
        method: "PATCH",
        body: JSON.stringify(body),
        auth: true,
      }),
    listAccepted: (params?: { mistake_type?: string }) => {
      const q = new URLSearchParams();
      if (params?.mistake_type) q.set("mistake_type", params.mistake_type);
      const suffix = q.toString() ? `?${q}` : "";
      return apiFetch<PaginatedLessonCandidates>(`/lessons/accepted${suffix}`, { auth: true });
    },
  },
};

export type { AuditRecord };
export { ApiError } from "@/lib/api/client";
