import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataNumber } from "@/components/ui/data-number";
import { RiskBlock } from "@/components/ui/risk-block";
import type { PaperExecutionView } from "@/lib/canonical-decision/types";

const TONE: Record<PaperExecutionView["status"], "success" | "pending" | "blocked" | "muted" | "warn"> = {
  not_started: "muted",
  blocked: "blocked",
  awaiting_submit: "pending",
  submitting: "pending",
  pending: "pending",
  filled: "success",
  cancelled: "warn",
  rejected: "blocked",
  unknown: "muted",
};

export function ExecutionLifecycle({ execution }: { execution: PaperExecutionView }) {
  return (
    <Card data-testid="execution-lifecycle">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Paper execution status</CardTitle>
          <StatusBadge label={execution.status.replaceAll("_", " ")} tone={TONE[execution.status]} />
          <StatusBadge
            label={
              execution.authority === "canonical" ? "canonical receipt" : "compatibility order"
            }
            tone={execution.authority === "canonical" ? "success" : "muted"}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-caption text-text-muted" data-testid="execution-paper-only">
          Mode: paper. Live execution available: never. This surface cannot send a real order.
        </p>
        {execution.blockReason ? (
          <RiskBlock reason={execution.blockReason} ruleReference="paper_execution_gate" />
        ) : null}
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-caption text-text-muted">Symbol</dt>
            <dd>{execution.symbol ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-caption text-text-muted">Side</dt>
            <dd>{execution.side ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-caption text-text-muted">Size</dt>
            <dd>
              <DataNumber value={execution.size ?? "—"} />
            </dd>
          </div>
          <div>
            <dt className="text-caption text-text-muted">Order</dt>
            <dd className="font-data break-all">{execution.orderId ?? "None"}</dd>
          </div>
          {execution.receiptId ? (
            <div>
              <dt className="text-caption text-text-muted">Receipt</dt>
              <dd className="font-data break-all">{execution.receiptId}</dd>
            </div>
          ) : null}
        </dl>
        {execution.proposalId ? (
          <Link href={`/decision/plans/${execution.proposalId}`} className="text-accent underline">
            Open TradePlan
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}
