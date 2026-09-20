"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ApprovalRequest, ExecutePaperPlanResult } from "@/lib/api/types";

function paperPlanIdempotencyKey(authorizationId: string): string {
  return `paper-plan:${authorizationId}`;
}

export function CanonicalPaperPlanButton({
  approval,
  onSuccess,
}: {
  approval: ApprovalRequest;
  onSuccess?: (result: ExecutePaperPlanResult) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExecutePaperPlanResult | null>(null);
  const authorization = approval.authorization;
  const revisionId = approval.plan_revision_id ?? authorization?.revision_id;
  const ready = Boolean(authorization && revisionId && authorization.account_id);

  async function execute() {
    if (!authorization || !revisionId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await api.execution.executePaperPlan({
        account_id: authorization.account_id,
        authorization_id: authorization.authorization_id,
        revision_id: revisionId,
        idempotency_key: paperPlanIdempotencyKey(authorization.authorization_id),
      });
      setResult(response);
      onSuccess?.(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Paper plan execution failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2" data-testid="canonical-paper-plan-button">
      <p className="text-caption text-text-muted">
        Canonical TradePlan execution uses POST /execution/paper-plan. Executable fields are
        forbidden. Legacy POST /execution/paper is not used.
      </p>
      <Button
        className="min-h-11"
        disabled={busy || !ready}
        onClick={() => void execute()}
        data-testid="execute-paper-plan-button"
      >
        Execute approved paper plan
      </Button>
      {result ? (
        <p className="text-caption" data-testid="paper-plan-outcome">
          {result.outcome}
          {result.replayed ? " (replayed)" : ""} · receipt {result.receipt.receipt_id}
        </p>
      ) : null}
      {error ? (
        <p className="text-caption text-danger" data-testid="paper-plan-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
