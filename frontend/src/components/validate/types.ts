import type { SourceResult } from "@/components/workflows/sourceResult";
import type {
  PaperValidationCandidateItem,
  PaperValidationDraftItem,
  PaperValidationRunPlanItem,
  PaperValidationRunSessionItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";

/** Ordered Validate pipeline stages (AT-040 Phase C2). */
export const VALIDATION_STAGE_ORDER = [
  "draft",
  "candidate",
  "run_plan",
  "run_session",
  "observation",
  "outcome",
] as const;

export type ValidationStageId = (typeof VALIDATION_STAGE_ORDER)[number];

export type ValidationStageDefinition = {
  id: ValidationStageId;
  name: string;
  purpose: string;
  href: string;
};

export const VALIDATION_STAGE_DEFINITIONS: readonly ValidationStageDefinition[] = [
  {
    id: "draft",
    name: "Draft",
    purpose: "Prep a paper idea from a reviewed setup before queueing validation.",
    href: "/paper-validation/drafts",
  },
  {
    id: "candidate",
    name: "Candidate",
    purpose: "Review and compare queued setups before planning a validation run.",
    href: "/paper-validation/candidates",
  },
  {
    id: "run_plan",
    name: "Run plan",
    purpose: "Define entry, invalidation, success, and failure criteria for observation.",
    href: "/paper-validation/run-plans",
  },
  {
    id: "run_session",
    name: "Run session",
    purpose: "Manually observe a planned setup in paper-only mode.",
    href: "/paper-validation/run-sessions",
  },
  {
    id: "observation",
    name: "Observation",
    purpose: "Record what happened during an active or completed session.",
    href: "/paper-validation/run-sessions",
  },
  {
    id: "outcome",
    name: "Outcome",
    purpose: "Capture success/failure, discipline notes, and validation limitations.",
    href: "/paper-validation/run-sessions",
  },
] as const;

export type ValidationCount = number | null;

export type ValidationStageModel = {
  id: ValidationStageId;
  name: string;
  purpose: string;
  href: string;
  count: ValidationCount;
  statusLabel: string;
  nextAction: string;
  blocker: string | null;
  timestamp: string | null;
  available: boolean;
  sourceName: string;
};

export type ValidationAttentionItem = {
  id: string;
  title: string;
  detail: string;
  href: string;
  stageId: ValidationStageId;
  urgency: "high" | "medium" | "low";
};

export type RecentOutcomeSummary = {
  sessionId: string;
  symbol: string | null;
  condition: string | null;
  sessionStatus: string;
  outcome: string | null;
  recordedAt: string | null;
  href: string;
  resultAvailable: boolean;
};

export type ValidationPipelineModel = {
  stages: ValidationStageModel[];
  counts: Record<ValidationStageId, ValidationCount>;
  attention: ValidationAttentionItem[];
  activeSessions: PaperValidationRunSessionItem[];
  recentOutcomes: RecentOutcomeSummary[];
  limitations: string[];
};

export type ValidationListPayload<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type ValidateHubSources = {
  drafts: SourceResult<ValidationListPayload<PaperValidationDraftItem>>;
  candidates: SourceResult<ValidationListPayload<PaperValidationCandidateItem>>;
  runPlans: SourceResult<ValidationListPayload<PaperValidationRunPlanItem>>;
  runSessions: SourceResult<ValidationListPayload<PaperValidationRunSessionItem>>;
  /** Optional per-session results for recent completed sessions only. */
  recentResults: SourceResult<PaperValidationSessionResultItem>[];
};
