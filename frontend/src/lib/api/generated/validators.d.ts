// Generated validators do not coerce, default, or strip values.
import type { ValidateFunction } from "ajv";
import type { components } from "./types";
export const agentTurnResponse: ValidateFunction<components["schemas"]["AgentTurnResult"]>;
export const agentTurnRequest: ValidateFunction<components["schemas"]["AgentTurnRequest"]>;
export const confirmProposalResponse: ValidateFunction<components["schemas"]["StructuredActionProposal"]>;
export const confirmProposalRequest: ValidateFunction<components["schemas"]["ProposalDecisionRequest"]>;
export const rejectProposalResponse: ValidateFunction<components["schemas"]["StructuredActionProposal"]>;
export const rejectProposalRequest: ValidateFunction<components["schemas"]["ProposalDecisionRequest"]>;
export const strategyPatchResponse: ValidateFunction<components["schemas"]["UserStrategy"]>;
export const strategyPatchRequest: ValidateFunction<components["schemas"]["UserStrategyUpdate"]>;
export const attentionResponse: ValidateFunction<components["schemas"]["AttentionQueue"]>;
export const dailyReviewResponse: ValidateFunction<components["schemas"]["DailyReview"]>;
