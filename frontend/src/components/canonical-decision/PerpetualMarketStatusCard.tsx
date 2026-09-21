import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FreshnessPill } from "@/components/ui/freshness-pill";
import { availabilityFreshnessState } from "@/lib/canonical-decision/compose";
import type { PerpetualMarketStatusView } from "@/lib/canonical-decision/types";
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

function presentationLabel(presentation: string): string {
  return PRESENTATION_LABEL[presentation] ?? presentation.replaceAll("_", " ");
}

export function PerpetualMarketStatusCard({ status }: { status: PerpetualMarketStatusView }) {
  const price = status.currentPrice;
  const usable = price.usableAsCurrentMarketPrice;
  const shown =
    usable || price.presentation === "replay_fixture" ? price.price : null;
  return (
    <Card data-testid="perpetual-market-status">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Perpetual market status</CardTitle>
          <FreshnessPill state={availabilityFreshnessState(status.availability)} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-text-secondary">{status.summary}</p>
        <div
          className="rounded-control border border-border-subtle bg-surface-0 p-3"
          data-testid="monitor-current-price"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-medium text-text-primary">Current perpetual price</p>
            <StatusBadge
              label={status.mode === "replay" ? "Replay" : "Perpetual"}
              tone={status.mode === "replay" ? "paper" : "info"}
            />
          </div>
          <p className="mt-1 text-lg font-medium text-text-primary" data-testid="monitor-current-price-value">
            {formatPrice(shown)}
          </p>
          <p className="mt-1 text-caption text-text-muted" data-testid="monitor-current-price-label">
            {usable
              ? `${presentationLabel(price.presentation)} · last update ${status.lastUpdate ?? "unknown"}`
              : `${presentationLabel(price.presentation)} — not a current live perpetual price`}
          </p>
        </div>
        <ul className="space-y-2">
          <li className="rounded-control bg-surface-0 p-3">
            <p className="font-medium text-text-primary">Source</p>
            <p className="mt-1 text-text-secondary">
              {status.sourceLabel} · {status.providerName} ({status.providerHealth})
            </p>
          </li>
          <li className="rounded-control bg-surface-0 p-3">
            <p className="font-medium text-text-primary">Trade stream</p>
            <p className="mt-1 text-text-secondary">{status.streamLabel}</p>
          </li>
          <li className="rounded-control bg-surface-0 p-3">
            <p className="font-medium text-text-primary">OHLCV</p>
            <p className="mt-1 text-text-secondary">{status.ohlcvLabel}</p>
          </li>
          <li className="rounded-control bg-surface-0 p-3">
            <p className="font-medium text-text-primary">CVD / aggressive flow</p>
            <p className="mt-1 text-text-secondary">{status.cvdLabel}</p>
          </li>
        </ul>
        <p className="text-caption text-text-muted" data-testid="monitor-watcher-off">
          Watcher is not activated. Compatibility and demo-seed prices are not current live marks.
        </p>
      </CardContent>
    </Card>
  );
}
