// Generated from local FastAPI OpenAPI. Run npm run api:generate.
import type { paths } from "./types";
import { validatedFetch } from "../validated-fetch";
import * as validators from "./validators";

export function agentTurn(body: paths["/agent/turns"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/agent/turns"]["post"]["responses"][200]["content"]["application/json"]>("/agent/turns", {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.agentTurnRequest,
    errorValidators: { 409: validators.agentTurnError409, 422: validators.agentTurnError422 },
    responseValidator: validators.agentTurnResponse,
  });
}

export function chatMessage(body: paths["/chat/message"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/chat/message"]["post"]["responses"][200]["content"]["application/json"]>("/chat/message", {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.chatMessageRequest,
    errorValidators: { 409: validators.chatMessageError409, 422: validators.chatMessageError422 },
    responseValidator: validators.chatMessageResponse,
  });
}

export function captureRetry(body: paths["/agent/saved/retry"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/agent/saved/retry"]["post"]["responses"][200]["content"]["application/json"]>("/agent/saved/retry", {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.captureRetryRequest,
    errorValidators: { 409: validators.captureRetryError409, 422: validators.captureRetryError422 },
    responseValidator: validators.captureRetryResponse,
  });
}

export function knowledgeDocuments(query?: paths["/knowledge/documents"]["get"]["parameters"]["query"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/knowledge/documents"]["get"]["responses"][200]["content"]["application/json"]>("/knowledge/documents", {
    method: "GET", auth: true, signal: options?.signal, headers: options?.headers,
    query,
    errorValidators: { 422: validators.knowledgeDocumentsError422 },
    responseValidator: validators.knowledgeDocumentsResponse,
  });
}

export function knowledgeChunks(query?: paths["/knowledge/chunks"]["get"]["parameters"]["query"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/knowledge/chunks"]["get"]["responses"][200]["content"]["application/json"]>("/knowledge/chunks", {
    method: "GET", auth: true, signal: options?.signal, headers: options?.headers,
    query,
    errorValidators: { 422: validators.knowledgeChunksError422 },
    responseValidator: validators.knowledgeChunksResponse,
  });
}

export function knowledgeIngest(body: paths["/knowledge/ingest"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/knowledge/ingest"]["post"]["responses"][200]["content"]["application/json"]>("/knowledge/ingest", {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.knowledgeIngestRequest,
    errorValidators: { 422: validators.knowledgeIngestError422 },
    responseValidator: validators.knowledgeIngestResponse,
  });
}

export function knowledgeRetryIndexing(id: paths["/knowledge/documents/{document_id}/retry-indexing"]["post"]["parameters"]["path"]["document_id"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/knowledge/documents/{document_id}/retry-indexing"]["post"]["responses"][200]["content"]["application/json"]>(`/knowledge/documents/${encodeURIComponent(id)}/retry-indexing`, {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    errorValidators: { 422: validators.knowledgeRetryIndexingError422 },
    responseValidator: validators.knowledgeRetryIndexingResponse,
  });
}

export function confirmProposal(id: paths["/agent/proposals/{proposal_id}/confirm"]["post"]["parameters"]["path"]["proposal_id"], body: paths["/agent/proposals/{proposal_id}/confirm"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/agent/proposals/{proposal_id}/confirm"]["post"]["responses"][200]["content"]["application/json"]>(`/agent/proposals/${encodeURIComponent(id)}/confirm`, {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.confirmProposalRequest,
    errorValidators: { 422: validators.confirmProposalError422 },
    responseValidator: validators.confirmProposalResponse,
  });
}

export function rejectProposal(id: paths["/agent/proposals/{proposal_id}/reject"]["post"]["parameters"]["path"]["proposal_id"], body: paths["/agent/proposals/{proposal_id}/reject"]["post"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/agent/proposals/{proposal_id}/reject"]["post"]["responses"][200]["content"]["application/json"]>(`/agent/proposals/${encodeURIComponent(id)}/reject`, {
    method: "POST", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.rejectProposalRequest,
    errorValidators: { 422: validators.rejectProposalError422 },
    responseValidator: validators.rejectProposalResponse,
  });
}

export function strategyPatch(id: paths["/strategies/{strategy_id}"]["patch"]["parameters"]["path"]["strategy_id"], body: paths["/strategies/{strategy_id}"]["patch"]["requestBody"]["content"]["application/json"], options?: { signal?: AbortSignal; headers?: Record<string, string> }) {
  return validatedFetch<paths["/strategies/{strategy_id}"]["patch"]["responses"][200]["content"]["application/json"]>(`/strategies/${encodeURIComponent(id)}`, {
    method: "PATCH", auth: true, signal: options?.signal, headers: options?.headers,
    bodyValue: body, requestValidator: validators.strategyPatchRequest,
    errorValidators: { 422: validators.strategyPatchError422 },
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
    errorValidators: { 422: validators.dailyReviewError422 },
    responseValidator: validators.dailyReviewResponse,
  });
}
