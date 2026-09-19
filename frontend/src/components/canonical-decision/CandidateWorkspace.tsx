import Link from "next/link";

import { ActionEligibilityCard } from "@/components/canonical-decision/ActionEligibilityCard";
import { MarketQualityCard } from "@/components/canonical-decision/MarketQualityCard";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CandidateWorkspaceView } from "@/lib/canonical-decision/types";

export function CandidateWorkspace({ candidate }: { candidate: CandidateWorkspaceView }) {
  return (
    <div className="space-y-4" data-testid="candidate-workspace">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>
              {candidate.symbol ?? "Candidate"} · {candidate.setupLabel ?? "setup"}
            </CardTitle>
            <StatusBadge
              label={candidate.lifecycleState.replaceAll("_", " ")}
              tone="pending"
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex flex-wrap gap-2">
            <Badge variant="muted">{candidate.authority.replaceAll("_", " ")}</Badge>
            <ConfidenceBadge value={candidate.confidence} />
            {candidate.direction ? <Badge variant="default">{candidate.direction}</Badge> : null}
            {candidate.timeframe ? <Badge variant="muted">{candidate.timeframe}</Badge> : null}
          </div>
          {candidate.thesis ? <p className="text-text-secondary">{candidate.thesis}</p> : null}
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-caption text-text-muted">Entry / setup</dt>
              <dd className="text-text-primary">{candidate.entryCriteria ?? "Not specified"}</dd>
            </div>
            <div>
              <dt className="text-caption text-text-muted">Invalidation</dt>
              <dd className="text-text-primary">{candidate.invalidation ?? "Not specified"}</dd>
            </div>
          </dl>
          {candidate.legacyHref ? (
            <Link href={candidate.legacyHref} className="text-sm text-accent underline">
              Open legacy validation candidate
            </Link>
          ) : null}
          <p className="text-caption text-text-muted" data-testid="candidate-authority-copy">
            {candidate.authority === "canonical"
              ? "Canonical Candidate read. This workspace does not mint a TradePlan by itself."
              : "Compatibility projection from the paper-validation queue. Not canonical Candidate authority."}
          </p>
        </CardContent>
      </Card>
      <div className="grid gap-4 xl:grid-cols-2">
        <MarketQualityCard quality={candidate.marketQuality} />
        <ActionEligibilityCard eligibility={candidate.eligibility} />
      </div>
    </div>
  );
}
