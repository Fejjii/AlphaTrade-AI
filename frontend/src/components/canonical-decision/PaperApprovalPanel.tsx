"use client";

import { useState } from "react";

import { CanonicalPaperPlanButton } from "@/components/canonical-decision/CanonicalPaperPlanButton";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApprovalRequest, TradeProposal } from "@/lib/api/types";
import type { PaperApprovalView } from "@/lib/canonical-decision/types";

export function PaperApprovalPanel({
  approval,
  proposal,
  busy,
  onApprove,
  onReject,
  onRefresh,
}: {
  approval: PaperApprovalView | ApprovalRequest;
  proposal: TradeProposal | null;
  busy?: boolean;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  onRefresh?: () => void;
}) {
  const [confirmText, setConfirmText] = useState("");
  const isApprovalRequest = "id" in approval;
  const approvalRequest = isApprovalRequest ? approval : null;
  const approvalId = isApprovalRequest ? approval.id : approval.approvalId;
  const status = approval.status;
  const pending = status === "pending";
  const confirmOk = confirmText.trim().toLowerCase() === "approve paper";

  return (
    <Card data-testid="paper-approval-panel">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Paper approval</CardTitle>
          <StatusBadge label={status.replaceAll("_", " ")} tone="pending" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p data-testid="approval-does-not-execute">
          Approving records human authorization for this exact paper plan. It does not place a
          paper order. AI output cannot replace this step.
        </p>
        <p className="text-caption text-text-muted">
          Live execution controls are not available. Real trading remains disabled.
        </p>
        {pending && onApprove && onReject ? (
          <div className="space-y-3 rounded-card border border-border-subtle p-3">
            <label className="block text-caption text-text-muted" htmlFor="approve-paper-confirm">
              Type <span className="font-data">approve paper</span> to enable human approval
            </label>
            <input
              id="approve-paper-confirm"
              className="min-h-11 w-full rounded-control border border-border bg-surface-0 px-3 text-sm"
              value={confirmText}
              onChange={(event) => setConfirmText(event.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                className="min-h-11"
                disabled={busy || !confirmOk}
                onClick={() => onApprove(approvalId)}
                data-testid="approve-paper-button"
              >
                Approve (paper authorization)
              </Button>
              <Button
                className="min-h-11"
                variant="destructive"
                disabled={busy}
                onClick={() => onReject(approvalId)}
              >
                Reject
              </Button>
            </div>
          </div>
        ) : null}
        {proposal ? (
          <div className="space-y-2 rounded-card border border-border-subtle p-3">
            <p className="text-caption uppercase tracking-wide text-text-muted">
              Separate paper execution
            </p>
            {approvalRequest ? (
              <CanonicalPaperPlanButton approval={approvalRequest} onSuccess={() => onRefresh?.()} />
            ) : (
              <p className="text-caption text-text-muted" data-testid="decision-paper-plan-only">
                Canonical decision execution uses POST /execution/paper-plan only. This approval
                has no bound plan revision authorization yet, so paper execution stays disabled
                here.
              </p>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
