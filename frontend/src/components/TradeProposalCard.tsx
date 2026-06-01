import Link from "next/link";

import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { RiskBadge } from "@/components/RiskBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TradeProposal } from "@/lib/api/types";
import { formatDate, formatDecimal } from "@/lib/utils";

export function TradeProposalCard({ proposal }: { proposal: TradeProposal }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {proposal.symbol} · {proposal.direction.toUpperCase()}
          </CardTitle>
          <StatusBadge label={proposal.status.replaceAll("_", " ")} tone="pending" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <div className="flex flex-wrap gap-2">
          <RiskBadge level={proposal.risk_level} />
          <ConfidenceBadge value={proposal.confidence} />
          {proposal.approval_required ? (
            <StatusBadge label="Approval required" tone="warn" />
          ) : null}
        </div>
        <p className="text-zinc-400">{proposal.rationale}</p>
        <div className="grid gap-1 text-zinc-400 sm:grid-cols-2">
          <span>Entry: {formatDecimal(proposal.entry_price)}</span>
          <span>Stop: {formatDecimal(proposal.exit.stop_loss)}</span>
          <span>Size: {formatDecimal(proposal.position_size)}</span>
          <span>Created: {formatDate(proposal.created_at)}</span>
        </div>
        <Link href={`/proposals?id=${proposal.id}`} className="text-emerald-400 hover:underline">
          View proposal details
        </Link>
      </CardContent>
    </Card>
  );
}
