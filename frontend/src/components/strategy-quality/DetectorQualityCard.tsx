"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DetectorQualityReport } from "@/lib/api/types";

import {
  CALIBRATION_META,
  formatRate,
  formatScore,
  labelize,
  TRUST_META,
  VERDICT_META,
} from "./quality-display";

function RateStat({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="rounded border border-zinc-800 px-2 py-1.5">
      <p className="text-sm font-semibold text-zinc-100">{formatRate(value)}</p>
      <p className="text-zinc-500">{label}</p>
    </div>
  );
}

export function DetectorQualityCard({ report }: { report: DetectorQualityReport }) {
  const verdict = VERDICT_META[report.verdict];
  const trust = TRUST_META[report.trust_tier];
  const calibration = report.confidence_calibration;
  const calibrationMeta = CALIBRATION_META[calibration.calibration_label];

  return (
    <Card data-testid={`strategy-quality-detector-${report.condition}`}>
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="text-base">{report.condition}</CardTitle>
          <p className="mt-1 text-xs text-zinc-500">
            {report.detector_version ? `detector v${report.detector_version} · ` : ""}
            n={report.sample_size}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <StatusBadge label={verdict.label} tone={verdict.tone} />
          <span className="text-xs text-zinc-500" data-testid="strategy-quality-score">
            quality {formatScore(report.quality_score)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label={trust.label} tone={trust.tone} />
          {report.raw_quality_score !== null && report.raw_quality_score !== undefined ? (
            <span className="text-xs text-zinc-500">
              raw {formatScore(report.raw_quality_score)} before shrinkage
            </span>
          ) : null}
        </div>

        <div
          className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"
          data-testid="strategy-quality-rates"
        >
          <RateStat label="Success" value={report.success_rate} />
          <RateStat label="Failure" value={report.failure_rate} />
          <RateStat label="Invalidated" value={report.invalidated_rate} />
          <RateStat label="Invalidation hit" value={report.invalidation_hit_rate} />
          <RateStat label="Missed entry" value={report.missed_entry_rate} />
          <RateStat label="No trade" value={report.no_trade_rate} />
          <RateStat label="Behaved as expected" value={report.behaved_as_expected_rate} />
          <RateStat label="Should have avoided" value={report.should_have_avoided_rate} />
        </div>

        <div
          className="rounded border border-zinc-800 px-3 py-2 text-xs"
          data-testid="strategy-quality-calibration"
        >
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="font-medium text-zinc-400">Confidence calibration</span>
            <StatusBadge label={calibrationMeta.label} tone={calibrationMeta.tone} />
          </div>
          <p className="text-zinc-500">
            mean confidence {formatRate(calibration.mean_confidence)} vs success{" "}
            {formatRate(calibration.mean_success_rate)} · correlation{" "}
            {labelize(calibration.correlation)}
          </p>
        </div>

        {report.warnings.length ? (
          <ul className="space-y-1 text-xs" data-testid="strategy-quality-detector-warnings">
            {report.warnings.map((warning) => (
              <li
                key={warning.code}
                className={warning.severity === "warning" ? "text-amber-300" : "text-zinc-400"}
              >
                {warning.message}
              </li>
            ))}
          </ul>
        ) : null}

        {report.rationale.length ? (
          <ul className="list-disc space-y-1 pl-5 text-xs text-zinc-300">
            {report.rationale.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}

        {report.factors.length ? (
          <div>
            <p className="mb-1 text-xs font-medium text-zinc-400">Quality breakdown</p>
            <ul className="space-y-1">
              {report.factors.map((factor) => (
                <li
                  key={factor.code}
                  data-testid={`strategy-quality-factor-${factor.code}`}
                  className="flex items-start justify-between gap-2 text-xs"
                >
                  <span className="text-zinc-300">{factor.detail}</span>
                  <span
                    className={
                      factor.direction === "negative"
                        ? "text-red-400"
                        : factor.direction === "positive"
                          ? "text-emerald-400"
                          : "text-zinc-500"
                    }
                  >
                    {factor.contribution > 0 ? `+${factor.contribution}` : factor.contribution}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
