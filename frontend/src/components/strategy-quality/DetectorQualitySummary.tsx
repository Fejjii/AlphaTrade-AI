"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { StrategyQualitySummaryResponse } from "@/lib/api/types";

import { formatScore, TRUST_META, VERDICT_META } from "./quality-display";

export function DetectorQualitySummary({
  summary,
}: {
  summary: StrategyQualitySummaryResponse;
}) {
  return (
    <Card data-testid="strategy-quality-summary">
      <CardHeader>
        <CardTitle className="text-base">Detector performance overview</CardTitle>
        <p className="mt-1 text-xs text-zinc-500">
          {summary.detectors_with_data} of {summary.total_detectors} detectors have validated
          results ({summary.total_results} total). Read-only study guidance — this does not change
          strategy rules or recommend live trades.
        </p>
      </CardHeader>
      <CardContent className="space-y-5 text-sm text-zinc-300">
        <div>
          <p className="mb-2 text-xs font-medium text-zinc-400">By verdict</p>
          <div
            className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-5"
            data-testid="strategy-quality-verdict-counts"
          >
            {summary.by_verdict.map((row) => (
              <div
                key={row.verdict}
                data-testid={`strategy-quality-verdict-${row.verdict}`}
                className="rounded border border-zinc-800 px-2 py-1.5"
              >
                <p className="text-lg font-semibold text-zinc-100">{row.count}</p>
                <p className="text-zinc-500">{VERDICT_META[row.verdict].label}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-zinc-400">By evidence tier</p>
          <div
            className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"
            data-testid="strategy-quality-trust-counts"
          >
            {summary.by_trust_tier.map((row) => (
              <div
                key={row.trust_tier}
                data-testid={`strategy-quality-trust-${row.trust_tier}`}
                className="rounded border border-zinc-800 px-2 py-1.5"
              >
                <p className="text-lg font-semibold text-zinc-100">{row.count}</p>
                <p className="text-zinc-500">{TRUST_META[row.trust_tier].label}</p>
              </div>
            ))}
          </div>
        </div>

        {summary.ranked.length ? (
          <div>
            <p className="mb-2 text-xs font-medium text-zinc-400">
              Quality ranking (sufficient evidence only)
            </p>
            <ul className="space-y-1" data-testid="strategy-quality-ranking">
              {summary.ranked.map((item) => (
                <li
                  key={item.condition}
                  data-testid={`strategy-quality-rank-${item.condition}`}
                  className="flex items-center justify-between gap-2 rounded border border-zinc-800 px-3 py-1.5 text-xs"
                >
                  <span className="text-zinc-300">
                    {item.rank}. {item.condition}
                  </span>
                  <span className="flex items-center gap-2">
                    <StatusBadge
                      label={VERDICT_META[item.verdict].label}
                      tone={VERDICT_META[item.verdict].tone}
                    />
                    <span className="text-zinc-400">
                      score {formatScore(item.quality_score)} · n={item.sample_size}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {summary.warnings.length ? (
          <ul className="space-y-1 text-xs text-amber-300" data-testid="strategy-quality-warnings">
            {summary.warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
