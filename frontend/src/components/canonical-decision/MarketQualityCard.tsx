import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FreshnessPill, type FreshnessState } from "@/components/ui/freshness-pill";
import type {
  CurrentPriceHonesty,
  EvidenceFact,
  MarketQualityView,
} from "@/lib/canonical-decision/types";
import { formatPrice } from "@/lib/format";

const PRESENTATION_LABEL: Record<string, string> = {
  live_mark: "Live mark",
  replay_fixture: "Replay fixture",
  stale: "Stale",
  incomplete: "Incomplete",
  degraded: "Degraded",
  provider_unavailable: "Provider unavailable",
  spot_rejected: "Spot rejected",
  wrong_source: "Wrong source",
  wrong_instrument: "Wrong instrument",
  unavailable: "Unavailable",
};

function factFreshness(fact: EvidenceFact): FreshnessState | null {
  if (fact.freshnessState) return fact.freshnessState;
  if (fact.stale) return "stale";
  if (fact.fallbackUsed) return "fallback";
  if (fact.isLive) return "live";
  return null;
}

function presentationLabel(presentation: string): string {
  return PRESENTATION_LABEL[presentation] ?? presentation.replaceAll("_", " ");
}

function CurrentPricePanel({ price }: { price: CurrentPriceHonesty }) {
  const usable = price.usableAsCurrentMarketPrice;
  const shown = usable || price.presentation === "replay_fixture" ? price.price : null;
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-0 p-3"
      data-testid="canonical-current-price"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium text-text-primary">Current perpetual price</p>
        <FreshnessPill
          state={price.freshnessState}
          ageLabel={price.ageSeconds ? `${price.ageSeconds}s` : undefined}
        />
      </div>
      <p className="mt-1 text-lg font-medium text-text-primary" data-testid="canonical-current-price-value">
        {formatPrice(shown)}
      </p>
      <p className="mt-1 text-caption text-text-muted" data-testid="canonical-current-price-label">
        {usable
          ? `${presentationLabel(price.presentation)} · ${price.freshnessPolicyVersion}`
          : `${presentationLabel(price.presentation)} — not a current market price`}
      </p>
    </div>
  );
}

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
        {quality.currentPrice ? <CurrentPricePanel price={quality.currentPrice} /> : null}
        <div className="flex flex-wrap gap-2">
          <Badge variant="muted">Setup {quality.setupState.replaceAll("_", " ")}</Badge>
          <ConfidenceBadge value={quality.confidence} />
          {quality.dataQuality ? <Badge variant="muted">{quality.dataQuality}</Badge> : null}
          {quality.confidencePenaltyApplied ? (
            <Badge variant="warning">Confidence penalty</Badge>
          ) : null}
          {quality.authority === "canonical" ? (
            <Badge variant="muted">Watcher off</Badge>
          ) : (
            <Badge variant="muted">Compatibility</Badge>
          )}
        </div>
        <ul className="space-y-2">
          {quality.evidence.map((fact, index) => {
            const pill = factFreshness(fact);
            return (
              <li key={`${fact.label}-${index}`} className="rounded-control bg-surface-0 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-text-primary">{fact.label}</p>
                  {pill ? <FreshnessPill state={pill} /> : null}
                </div>
                <p className="mt-1 text-text-secondary">{fact.detail}</p>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
