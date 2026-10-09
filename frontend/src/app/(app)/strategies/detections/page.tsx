"use client";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useCallback } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
export default function DetectionsPage() {
  const params = useSearchParams();
  const router = useRouter();
  const loader = useCallback(() => api.strategyBrain.overview(), []);
  const { data, loading, error } = useAsyncData(loader, []);
  const all = params.get("history") === "all";
  const family = params.get("family") ?? "";
  const since = Date.now() - 7 * 86400000;
  const setups =
    data?.setups.filter(
      (s) =>
        (!family || s.family === family) &&
        (all || Date.parse(s.observed_at) >= since),
    ) ?? [];
  return (
    <div className="space-y-4">
      <Link href="/strategies" className="text-accent">
        ← Back to Strategies
      </Link>
      <h1 className="text-2xl font-semibold">Recent detections</h1>
      <p className="text-sm text-text-muted">
        Market observations · {all ? "All recorded history" : "Last 7 days"}
      </p>
      <div className="flex flex-wrap gap-3">
        <label>
          Family{" "}
          <select
            aria-label="Detection family"
            value={family}
            className="min-h-11 bg-surface-1"
            onChange={(e) => {
              const q = new URLSearchParams(params);
              q.set("family", e.target.value);
              router.replace(`?${q}`, { scroll: false });
            }}
          >
            <option value="">All</option>
            <option value="nested_continuation">Nested</option>
            <option value="sfp">SFP</option>
          </select>
        </label>
        <Link
          href={`/strategies/detections?history=${all ? "recent" : "all"}&family=${family}`}
          className="text-accent"
        >
          {all ? "Recent history" : "All history"}
        </Link>
      </div>
      {loading ? (
        <p>Loading…</p>
      ) : error ? (
        <p role="alert">Detections unavailable.</p>
      ) : !setups.length ? (
        <p>No matching detections.</p>
      ) : (
        <ul className="space-y-2">
          {setups.map((s) => (
            <li
              className="rounded-card border border-border-subtle p-3"
              key={s.setup_id}
            >
              <Link
                href={`/strategies/setups/${s.setup_id}?returnTo=${encodeURIComponent(`/strategies/detections?${params}`)}`}
                className="text-accent"
              >
                {s.symbol || s.instrument} · {s.direction} · {s.timeframe}
              </Link>
              <p className="text-sm text-text-muted">
                {s.family} · {s.state} · {formatDateTime(s.observed_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
