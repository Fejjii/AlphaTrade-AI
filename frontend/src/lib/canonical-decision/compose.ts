import type {
  ApprovalRequest,
  JournalEntry,
  LessonCandidate,
  MarketAnalyzeResponse,
  PaperOrder,
  PaperValidationCandidateItem,
  TradeProposal,
} from "@/lib/api/types";
import { projectActionEligibility } from "@/lib/canonical-decision/eligibility";
import {
  candidateSetupLabel,
  executionFromOrder,
  tradePlanFromProposal,
} from "@/lib/canonical-decision/trade-plan";
import type {
  CandidateLifecycleState,
  CandidateWorkspaceView,
  DecisionCase,
  DecisionQueueSnapshot,
  DecisionStage,
  EvidenceFact,
  LearningView,
  MarketQualityGrade,
  MarketQualityView,
  OutcomeView,
  PaperApprovalView,
  SetupAssessmentState,
} from "@/lib/canonical-decision/types";
import { DECISION_STAGES } from "@/lib/canonical-decision/types";
import { missingBindings } from "@/lib/canonical-decision/bindings";
import { canExecutePaperOrder } from "@/lib/workflow";

export type DecisionComposeInput = {
  candidates: PaperValidationCandidateItem[];
  proposals: TradeProposal[];
  approvals: ApprovalRequest[];
  orders: PaperOrder[];
  journals: JournalEntry[];
  lessons: LessonCandidate[];
  killSwitchActive: boolean;
  executionMode: string | null;
  realTradingEnabled: boolean | null;
};

function emptyStageCounts(): Record<DecisionStage, number> {
  return Object.fromEntries(DECISION_STAGES.map((stage) => [stage, 0])) as Record<
    DecisionStage,
    number
  >;
}

export function marketQualityFromAnalysis(
  analysis: MarketAnalyzeResponse,
  symbol: string,
  timeframe: string,
): MarketQualityView {
  const meta = analysis.snapshot.meta;
  const best = analysis.strategy_signals[0];
  const evidence: EvidenceFact[] = [
    {
      label: "Market data",
      detail: `${meta.source} · ${meta.provider_name}`,
      freshness: meta.retrieved_at,
      isLive: meta.is_live,
      fallbackUsed: meta.fallback_used,
      stale: meta.is_stale,
    },
    ...analysis.strategy_signals.flatMap((signal) =>
      signal.evidence.map((item) => ({
        label: signal.strategy_id,
        detail: item,
      })),
    ),
  ];
  const grade: MarketQualityGrade = meta.is_stale || meta.fallback_used
    ? "poor"
    : analysis.data_quality.toLowerCase().includes("poor")
      ? "poor"
      : best && (best.confidence ?? 0) >= 0.65
        ? "tradeable"
        : best
          ? "watch"
          : "unknown";
  const setupState: SetupAssessmentState =
    grade === "tradeable" ? "confirmed_setup" : grade === "watch" ? "watch" : "unknown";
  return {
    authority: "compatibility_projection",
    grade,
    setupState,
    dataQuality: analysis.data_quality,
    confidence: best?.confidence ?? null,
    confidencePenaltyApplied: analysis.confidence_penalty_applied,
    symbol,
    timeframe,
    direction: best?.direction ?? null,
    evidence,
    summary:
      grade === "poor"
        ? "Market quality is degraded. This does not by itself decide eligibility."
        : "Market quality is independent of account, risk, and kill-switch eligibility.",
    doesNotGrantEligibility: true,
  };
}

export function marketQualityFromCandidate(candidate: PaperValidationCandidateItem): MarketQualityView {
  const evidence: EvidenceFact[] = [];
  if (candidate.thesis) evidence.push({ label: "Thesis", detail: candidate.thesis });
  if (candidate.entry_criteria) evidence.push({ label: "Entry", detail: candidate.entry_criteria });
  if (candidate.invalidation_criteria) {
    evidence.push({ label: "Invalidation", detail: candidate.invalidation_criteria });
  }
  if (candidate.evidence_tier) {
    evidence.push({ label: "Evidence tier", detail: candidate.evidence_tier });
  }
  const grade: MarketQualityGrade =
    (candidate.confidence ?? 0) >= 0.65 ? "tradeable" : candidate.confidence != null ? "watch" : "unknown";
  return {
    authority: "compatibility_projection",
    grade,
    setupState: candidate.candidate_status === "archived" ? "expired" : "unknown",
    dataQuality: candidate.evidence_tier ?? null,
    confidence: candidate.confidence ?? null,
    confidencePenaltyApplied: false,
    symbol: candidate.symbol ?? null,
    timeframe: candidate.timeframe ?? null,
    direction: candidate.direction ?? null,
    evidence,
    summary:
      "Compatibility projection from the paper-validation queue. Not canonical SetupAssessment.",
    doesNotGrantEligibility: true,
  };
}

function lifecycleFromCandidate(candidate: PaperValidationCandidateItem): CandidateLifecycleState {
  if (candidate.candidate_status === "archived") return "skipped";
  if (candidate.candidate_status === "reviewing") return "active";
  return "active";
}

function approvalView(approval: ApprovalRequest | undefined): PaperApprovalView | null {
  if (!approval) return null;
  return {
    approvalId: approval.id,
    proposalId: approval.proposal_id,
    status: approval.status,
    createdAt: approval.created_at,
    decidedAt: approval.decided_at ?? null,
    reason: approval.approval_reason ?? null,
    humanApprovalRequired: true,
    aiCannotBypass: true,
    recordsAuthorizationOnly: true,
    doesNotPlaceOrder: true,
  };
}

function outcomeFromJournal(entry: JournalEntry | undefined): OutcomeView | null {
  if (!entry) return null;
  return {
    journalId: entry.id,
    positionId: entry.linked_position_id ?? null,
    proposalId: entry.linked_proposal_id ?? null,
    symbol: entry.symbol,
    result: entry.result,
    pnl: entry.pnl ?? null,
    lessons: entry.lessons ?? null,
    href: `/decision/outcomes/${entry.id}`,
  };
}

function learningFromLesson(lesson: LessonCandidate | undefined): LearningView | null {
  if (!lesson) return null;
  return {
    lessonId: lesson.id,
    status: lesson.status,
    lessonText: lesson.lesson_text,
    mistakeType: lesson.mistake_type,
    href: `/lessons?id=${lesson.id}`,
  };
}

export function deriveProposalStage(input: {
  proposal: TradeProposal;
  approval: ApprovalRequest | undefined;
  order: PaperOrder | undefined;
  journal: JournalEntry | undefined;
  lesson: LessonCandidate | undefined;
}): DecisionStage {
  if (input.lesson) return "learning";
  if (input.journal) return "outcome";
  if (input.order) return "paper_execution";
  if (input.approval) {
    if (input.approval.status === "approved") return "paper_execution";
    return "approval";
  }
  if (input.proposal.status === "approved") return "paper_execution";
  if (input.proposal.status === "pending_approval" || input.proposal.approval_required) {
    return "approval";
  }
  return "trade_plan";
}

function candidateWorkspaceFromPvc(
  candidate: PaperValidationCandidateItem,
  facts: Pick<DecisionComposeInput, "killSwitchActive" | "executionMode" | "realTradingEnabled">,
): CandidateWorkspaceView {
  const marketQuality = marketQualityFromCandidate(candidate);
  const actionable = candidate.candidate_status !== "archived";
  return {
    authority: "compatibility_projection",
    caseId: `pvc:${candidate.candidate_id}`,
    sourceId: candidate.candidate_id,
    sourceKind: "compatibility_candidate",
    lifecycleState: lifecycleFromCandidate(candidate),
    symbol: candidate.symbol ?? null,
    timeframe: candidate.timeframe ?? null,
    direction: candidate.direction ?? null,
    setupLabel: candidateSetupLabel(candidate),
    thesis: candidate.thesis ?? null,
    entryCriteria: candidate.entry_criteria ?? null,
    invalidation: candidate.invalidation_criteria ?? candidate.invalidation_level?.toString() ?? null,
    confidence: candidate.confidence ?? null,
    evidence: marketQuality.evidence,
    strategyId: candidate.strategy_id ?? null,
    createdAt: candidate.created_at,
    legacyHref: `/paper-validation/candidates/${candidate.candidate_id}`,
    marketQuality,
    eligibility: projectActionEligibility({
      killSwitchActive: facts.killSwitchActive,
      executionMode: facts.executionMode,
      realTradingEnabled: facts.realTradingEnabled,
      candidateActionable: actionable,
      setupConfirmed: marketQuality.grade === "tradeable",
    }),
  };
}

export function composeDecisionCases(input: DecisionComposeInput): DecisionQueueSnapshot {
  const approvalsByProposal = new Map(input.approvals.map((item) => [item.proposal_id, item]));
  const ordersByProposal = new Map(
    input.orders
      .filter((order) => order.proposal_id)
      .map((order) => [order.proposal_id as string, order]),
  );
  const journalsByProposal = new Map(
    input.journals
      .filter((entry) => entry.linked_proposal_id)
      .map((entry) => [entry.linked_proposal_id as string, entry]),
  );
  const lessonsByJournal = new Map(
    input.lessons
      .filter((lesson) => lesson.related_journal_entry_id)
      .map((lesson) => [lesson.related_journal_entry_id as string, lesson]),
  );

  const cases: DecisionCase[] = [];

  for (const proposal of input.proposals) {
    const approval = approvalsByProposal.get(proposal.id);
    const order = ordersByProposal.get(proposal.id);
    const journal = journalsByProposal.get(proposal.id);
    const lesson = journal ? lessonsByJournal.get(journal.id) : undefined;
    const stage = deriveProposalStage({ proposal, approval, order, journal, lesson });
    const paperGate = canExecutePaperOrder(proposal, approval);
    const tradePlan = tradePlanFromProposal(proposal);
    const eligibility = projectActionEligibility({
      killSwitchActive: input.killSwitchActive,
      executionMode: input.executionMode,
      realTradingEnabled: input.realTradingEnabled,
      proposal,
      approval,
      setupConfirmed: true,
    });
    const candidate: CandidateWorkspaceView = {
      authority: "compatibility_projection",
      caseId: `proposal:${proposal.id}`,
      sourceId: proposal.id,
      sourceKind: "legacy_proposal",
      lifecycleState: stage === "trade_plan" || stage === "approval" ? "plan_created" : "plan_created",
      symbol: proposal.symbol,
      timeframe: proposal.timeframe,
      direction: proposal.direction,
      setupLabel: proposal.strategy_id,
      thesis: proposal.rationale,
      entryCriteria: `Entry ${proposal.entry_price}`,
      invalidation: proposal.exit.invalidation,
      confidence: proposal.confidence,
      evidence: [{ label: "Rationale", detail: proposal.rationale }],
      strategyId: proposal.strategy_id,
      createdAt: proposal.created_at,
      legacyHref: `/proposals?id=${proposal.id}`,
      marketQuality: {
        authority: "compatibility_projection",
        grade: proposal.confidence >= 0.65 ? "tradeable" : "watch",
        setupState: "unknown",
        dataQuality: null,
        confidence: proposal.confidence,
        confidencePenaltyApplied: false,
        symbol: proposal.symbol,
        timeframe: proposal.timeframe,
        direction: proposal.direction,
        evidence: [{ label: "Proposal rationale", detail: proposal.rationale }],
        summary: "Proposal-derived market notes. Not canonical SetupAssessment.",
        doesNotGrantEligibility: true,
      },
      eligibility,
    };
    cases.push({
      id: `proposal:${proposal.id}`,
      kind: "legacy_proposal",
      stage,
      symbol: proposal.symbol,
      direction: proposal.direction,
      timeframe: proposal.timeframe,
      title: `${proposal.symbol} ${proposal.direction}`,
      summary: `${stage.replaceAll("_", " ")} · ${eligibility.state}`,
      href:
        stage === "outcome" && journal
          ? `/decision/outcomes/${journal.id}`
          : stage === "paper_execution" && order
            ? `/decision/executions/${order.id}`
            : approval
              ? `/decision/approvals/${approval.id}`
              : `/decision/plans/${proposal.id}`,
      createdAt: proposal.created_at,
      candidate,
      tradePlan,
      approval: approvalView(approval),
      execution: executionFromOrder(
        order ?? null,
        proposal,
        approval ?? null,
        paperGate.allowed ? null : paperGate.reason ?? null,
      ),
      outcome: outcomeFromJournal(journal),
      learning: learningFromLesson(lesson),
    });
  }

  for (const candidate of input.candidates) {
    const workspace = candidateWorkspaceFromPvc(candidate, input);
    const stage: DecisionStage =
      workspace.eligibility.state === "blocked" ? "eligibility" : "candidate";
    cases.push({
      id: workspace.caseId,
      kind: "compatibility_candidate",
      stage,
      symbol: candidate.symbol ?? "Unknown",
      direction: candidate.direction ?? null,
      timeframe: candidate.timeframe ?? null,
      title: `${candidate.symbol ?? "Candidate"} · ${candidateSetupLabel(candidate)}`,
      summary: `${workspace.lifecycleState.replaceAll("_", " ")} · ${workspace.eligibility.state}`,
      href: `/decision/candidates/${candidate.candidate_id}`,
      createdAt: candidate.created_at,
      candidate: workspace,
      tradePlan: null,
      approval: null,
      execution: null,
      outcome: null,
      learning: null,
    });
  }

  cases.sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""));
  const stageCounts = emptyStageCounts();
  for (const item of cases) {
    stageCounts[item.stage] += 1;
  }
  return {
    cases,
    stageCounts,
    missingBindings: missingBindings().map((item) => item.id),
  };
}
