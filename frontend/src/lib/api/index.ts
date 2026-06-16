import { apiFetch } from "@/lib/api/client";
import type {
  AgentMessageResponse,
  ApprovalRequest,
  AuditRecord,
  AuthResponse,
  HealthResponse,
  IngestDocumentResponse,
  DisciplineScoreResult,
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
  PreTradeAnalyzeResponse,
  PositionSizingResult,
  HumanVsSystemComparison,
  UserStrategy,
  BacktestRun,
  PaginatedBacktestRuns,
  PaginatedBacktestTrades,
  PaperValidationSummary,
  MarketSnapshotResponse,
  OHLCVResponse,
  TickerResponse,
  WatchlistItem,
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
    startPaperValidation: (id: string) =>
      apiFetch<{ id: string; status: string }>(`/strategies/${id}/paper-validation/start`, {
        method: "POST",
        auth: true,
      }),
    paperValidation: (id: string) =>
      apiFetch<PaperValidationSummary>(`/strategies/${id}/paper-validation`, { auth: true }),
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
  },
};

export type { AuditRecord };
export { ApiError } from "@/lib/api/client";
