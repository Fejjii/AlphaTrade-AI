// Generated from local FastAPI OpenAPI. Run npm run api:generate.
import type { paths } from "./types";
import { validatedFetch } from "../validated-fetch";
import * as validators from "./validators";

export function agentTurn(body: paths["/agent/turns"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/agent/turns"]["post"]["responses"][200]["content"]["application/json"]>("/agent/turns", {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.agentTurnRequest,
    responseValidator: validators.agentTurnResponse,
  });
}

export function confirmProposal(id: paths["/agent/proposals/{proposal_id}/confirm"]["post"]["parameters"]["path"]["proposal_id"], body: paths["/agent/proposals/{proposal_id}/confirm"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/agent/proposals/{proposal_id}/confirm"]["post"]["responses"][200]["content"]["application/json"]>(`/agent/proposals/${encodeURIComponent(id)}/confirm`, {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.confirmProposalRequest,
    responseValidator: validators.confirmProposalResponse,
  });
}

export function rejectProposal(id: paths["/agent/proposals/{proposal_id}/reject"]["post"]["parameters"]["path"]["proposal_id"], body: paths["/agent/proposals/{proposal_id}/reject"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/agent/proposals/{proposal_id}/reject"]["post"]["responses"][200]["content"]["application/json"]>(`/agent/proposals/${encodeURIComponent(id)}/reject`, {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.rejectProposalRequest,
    responseValidator: validators.rejectProposalResponse,
  });
}

export function strategyPatch(id: paths["/strategies/{strategy_id}"]["patch"]["parameters"]["path"]["strategy_id"], body: paths["/strategies/{strategy_id}"]["patch"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/strategies/{strategy_id}"]["patch"]["responses"][200]["content"]["application/json"]>(`/strategies/${encodeURIComponent(id)}`, {
    method: "PATCH", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.strategyPatchRequest,
    responseValidator: validators.strategyPatchResponse,
  });
}

export function attention(options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/dashboard/attention"]["get"]["responses"][200]["content"]["application/json"]>("/dashboard/attention", {
    method: "GET", auth: true, signal: options?.signal, headers: options?.headers,
    responseValidator: validators.attentionResponse,
  });
}

export function dailyReview(query?: paths["/dashboard/daily-review"]["get"]["parameters"]["query"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/dashboard/daily-review"]["get"]["responses"][200]["content"]["application/json"]>("/dashboard/daily-review", {
    method: "GET", auth: true, signal: options?.signal, headers: options?.headers,
    query,
    responseValidator: validators.dailyReviewResponse,
  });
}
