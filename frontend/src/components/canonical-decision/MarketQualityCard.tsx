import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FreshnessPill } from "@/components/ui/freshness-pill";
import type { MarketQualityView } from "@/lib/canonical-decision/types";

export function MarketQualityCard({ quality }: { quality: MarketQualityView }) {
  return (
    <Card data-testid="market-quality-card">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Market quality</CardTitle>
          <StatusBadge label={quality.grade.replaceAll("_", " ")} tone="info" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-text-secondary">{quality.summary}</p>
        <p className="text-caption text-text-muted" data-testid="market-quality-separation">
          Market quality is not action eligibility. A strong setup still needs a separate paper
          gate.
        </p>
        <div className="flex flex-wrap gap-2">
          <Badge variant="muted">Setup {quality.setupState.replaceAll("_", " ")}</Badge>
          <ConfidenceBadge value={quality.confidence} />
          {quality.dataQuality ? <Badge variant="muted">{quality.dataQuality}</Badge> : null}
          {quality.confidencePenaltyApplied ? (
            <Badge variant="warning">Confidence penalty</Badge>
          ) : null}
        </div>
        <ul className="space-y-2">
          {quality.evidence.map((fact, index) => (
            <li key={`${fact.label}-${index}`} className="rounded-control bg-surface-0 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium text-text-primary">{fact.label}</p>
                {fact.stale != null || fact.fallbackUsed != null ? (
                  <FreshnessPill
                    state={fact.stale ? "stale" : fact.fallbackUsed ? "fallback" : "live"}
                  />
                ) : null}
              </div>
              <p className="mt-1 text-text-secondary">{fact.detail}</p>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
