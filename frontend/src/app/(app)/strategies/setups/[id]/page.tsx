"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import { displayedBrainSetup, useBrainSetupClock } from "@/hooks/useBrainSetupClock";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function NestedSetupPage() {
  const { id } = useParams<{ id: string }>();
  const loader = useCallback(() => api.strategyBrain.setup(id), [id]);
  const { data: stored, loading, error } = useAsyncData(loader, [id]);
  const setups = useMemo(() => stored ? [stored] : [], [stored]);
  const now = useBrainSetupClock(setups);
  const data = stored ? displayedBrainSetup(stored, now) : null;
  if (loading && !data) return <p>Loading setup history…</p>;
  if (error || !data) return <p role="alert">{error || "Setup unavailable"}</p>;
  return <div className="space-y-4 p-4">
    <Link href="/strategies" className="underline">Strategies</Link>
    <h1 className="text-xl">Nested {data.stage} · {data.state}</h1>
    <p>{data.instrument} · {data.direction} · evidence {data.freshness}</p>
    <p>Strategy version {data.strategy_version_id}</p>
    <p>Observed {data.observed_at} · expires {data.expires_at}</p>
    <p>Risk: {data.risk_state}. {data.reason_codes.join(", ")}</p>
    <p>Entry concept {data.entry ?? "unknown"} · stop {data.stop ?? "unknown"} · structural targets {data.targets.join(", ") || "none supported"}</p>
    <p className="break-all">Evidence reference {data.evidence_reference}</p>
    <ul>{Object.entries(data.evidence).map(([name, state]) => <li key={name}>{name}: {state}</li>)}</ul>
    {data.candidate_id && <Link href={`/decision/candidates/${data.candidate_id}`} className="block underline">Governed Candidate</Link>}
    {data.journal && <p>Journal <Link href="/journal" className="underline">{data.journal.id}</Link> · {data.journal.status} · realized PnL {data.journal.net_pnl ?? "not available"}</p>}
    <h2>Stored lifecycle</h2>
    <ul className="space-y-3">{data.history?.map(event => <li key={event.record_id} className="break-words rounded border border-border p-3">{event.occurred_at} · {event.kind}<p className="text-sm">{String(event.payload.state || event.payload.observation || event.payload.provenance || "Stored record")}</p></li>)}</ul>
    <p>Insufficient history for expectancy. User observations, system detections and actual outcomes remain distinct.</p>
  </div>;
}
