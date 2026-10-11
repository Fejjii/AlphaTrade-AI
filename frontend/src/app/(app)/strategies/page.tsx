"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback } from "react";
import { RiskSettingsSummary } from "@/components/settings/RiskSettingsSummary";
import { ExperimentsPanel } from "@/components/strategies/ExperimentsPanel";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { savedEntries } from "@/lib/api/saved-entries";
import { strategyStatusFor } from "@/lib/strategy-status";

const families = [
  {
    id: "nested",
    name: "Nested Continuation",
    kind: "operational_nested_continuation/v1",
  },
  { id: "sfp", name: "SFP", kind: "swing_failure_pattern/v1" },
];
export default function StrategiesPage() {
  const params = useSearchParams();
  const family = families.find((f) => f.id === params.get("family"));
  const loader = useCallback(async () => {
    const [brain, library, drafts] = await Promise.allSettled([
      api.strategyBrain.overview(),
      api.strategies.list({ limit: 50 }),
      savedEntries.list({ category: "strategies" }),
    ]);
    return {
      brain: brain.status === "fulfilled" ? brain.value : null,
      library: library.status === "fulfilled" ? library.value.items : null,
      drafts: drafts.status === "fulfilled" ? drafts.value.items : null,
    };
  }, []);
  const { data, loading, reload } = useAsyncData(loader, []);
  return (
    <div className="space-y-5" data-testid="trader-strategies">
      <div className="flex flex-wrap justify-between gap-3">
        <h1 className="text-2xl font-semibold">
          {family?.name ?? "Strategies"}
        </h1>
        <Link href="/agent?discuss=strategy" className="text-accent">
          Discuss a strategy
        </Link>
      </div>
      {family ? (
        <>
          <Link
            href="/strategies"
            className="inline-flex min-h-11 items-center text-accent"
          >
            ← Back to Strategies
          </Link>
          {data?.brain?.strategies
            .filter((s) => s.spec.kind === family.kind)
            .map((s) => (
              <article
                key={s.version_id}
                className="space-y-2 rounded-card border border-border-subtle p-4"
              >
                <div className="flex flex-wrap justify-between gap-2">
                  <h2 className="font-semibold">
                    {s.spec.symbol} · {s.spec.direction} ·{" "}
                    {s.spec.trigger_timeframe}
                  </h2>
                  <span className="text-sm">
                    {s.status} · v{s.version}
                  </span>
                </div>
                <p className="text-sm text-text-muted">
                  Approval, validation and automation are separate.
                </p>
                <Link
                  href={`/strategy-lab/${s.strategy_id}`}
                  className="inline-flex min-h-11 items-center text-accent"
                >
                  Open configuration &amp; revisions
                </Link>
                <details>
                  <summary className="min-h-11 cursor-pointer text-sm">
                    Rules &amp; evidence
                  </summary>
                  <pre className="overflow-auto whitespace-pre-wrap text-xs">
                    {JSON.stringify(s.spec, null, 2)}
                  </pre>
                </details>
              </article>
            ))}
          {!loading && !data?.brain && (
            <p role="status">Configurations unavailable.</p>
          )}
        </>
      ) : (
        <>
          <ExperimentsPanel initialExperiment={params.get("experiment")} />
          <h2 className="text-lg font-semibold">Strategy library</h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {families.map((f) => {
              const configs = data?.brain?.strategies.filter(
                (s) => s.spec.kind === f.kind,
              );
              return (
                <article
                  key={f.id}
                  data-testid="strategy-family"
                  className="space-y-3 rounded-card border border-border-subtle bg-surface-1 p-4"
                >
                  <h2 className="text-lg font-semibold">{f.name}</h2>
                  <p className="text-sm text-text-secondary">
                    {loading
                      ? "Loading…"
                      : !configs
                        ? "Configurations unavailable"
                        : `${configs.length} directional configurations`}
                  </p>
                  <div className="flex gap-4 text-sm text-accent">
                    <Link href={`/strategies?family=${f.id}`}>Open</Link>
                    <Link href={`/agent?discuss=${f.id}`}>Ask Agent</Link>
                  </div>
                </article>
              );
            })}
          </div>
          <Link
            href="/strategies/detections"
            className="inline-flex min-h-11 items-center text-accent"
          >
            Recent detections →
          </Link>
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">
              Drafts &amp; other strategies
            </h2>
            {data?.drafts?.map((d) => (
              <article
                key={d.id}
                className="space-y-2 rounded-card border border-border-subtle p-4"
              >
                <div className="flex justify-between gap-2">
                  <h3 className="font-medium">{d.title}</h3>
                  <span className="text-sm">Draft · v{d.revision}</span>
                </div>
                <p className="text-sm text-text-secondary">{d.summary}</p>
                <Link
                  href={`/journal?tab=knowledge&saved=${d.id}`}
                  className="text-accent"
                >
                  Open reviewable draft
                </Link>
              </article>
            ))}
            {data?.library
              ?.filter(
                (s) =>
                  !data.brain?.strategies.some((b) => b.strategy_id === s.id),
              )
              .map((s) => (
                <article
                  key={s.id}
                  className="flex flex-wrap justify-between gap-3 rounded-card border border-border-subtle p-4"
                >
                  <Link href={`/strategy-lab/${s.id}`} className="text-accent">
                    {s.latest_card?.strategy_name || s.name}
                  </Link>
                  <span className="text-sm">{strategyStatusFor(s).label}</span>
                </article>
              ))}
            {!loading &&
              data?.drafts?.length === 0 &&
              data?.library?.length === 0 && (
                <p className="text-sm text-text-muted">
                  Discuss your rules with Agent to create a draft.
                </p>
              )}
            <Button
              variant="outline"
              size="sm"
              disabled={loading}
              onClick={() => void reload()}
            >
              Refresh strategies
            </Button>
          </section>
        </>
      )}
      <details
        className="rounded-card border border-border-subtle p-4"
        id="risk"
      >
        <summary className="min-h-11 cursor-pointer font-semibold">
          Risk Policy
        </summary>
        <div className="space-y-3 pt-3">
          <RiskSettingsSummary />
          <Link href="/risk" className="text-accent">
            Configure account limits
          </Link>
          <p className="text-sm text-text-muted">
            Strategy limits remain bounded by the enforced account policy.
          </p>
        </div>
      </details>
    </div>
  );
}
