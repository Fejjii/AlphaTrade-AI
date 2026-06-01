"use client";

import { ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";

export function PaperModeBanner() {
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const { providers, health } = useAppContext();

  const marketProvider = providers?.providers.find((p) => p.kind === "market_data");
  const llmProvider = providers?.providers.find((p) => p.kind === "llm");
  const embeddingProvider = providers?.providers.find((p) => p.kind === "embeddings");
  const vectorProvider = providers?.providers.find((p) => p.kind === "vector");
  const redisProvider = providers?.providers.find((p) => p.name.toLowerCase().includes("redis"));

  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-emerald-300">
          <ShieldCheck className="h-4 w-4" />
          <span className="text-sm font-medium">Paper mode active</span>
        </div>
        <Badge variant="success">{executionMode.toUpperCase()}</Badge>
        <Badge variant={realTradingEnabled ? "danger" : "success"}>
          Real trading {realTradingEnabled ? "enabled" : "disabled"}
        </Badge>
        <Badge variant="info">Provider mode: {providerMode}</Badge>
      </div>
      <p className="mt-2 text-sm text-zinc-400">
        No real exchange orders are placed. Approvals gate paper execution only. Market data is
        read-only (Binance public API or mock fallback).
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {marketProvider ? (
          <Badge variant={marketProvider.is_mock ? "warning" : "info"}>
            Market: {marketProvider.name}
            {marketProvider.using_fallback ? " (fallback)" : ""}
          </Badge>
        ) : null}
        {llmProvider ? <Badge variant="muted">LLM: {llmProvider.name}</Badge> : null}
        {embeddingProvider ? (
          <Badge variant="muted">Embeddings: {embeddingProvider.name}</Badge>
        ) : null}
        {vectorProvider ? <Badge variant="muted">Qdrant: {vectorProvider.name}</Badge> : null}
        {redisProvider ? <Badge variant="muted">Redis: {redisProvider.health}</Badge> : null}
        {health ? <Badge variant="muted">API {health.status}</Badge> : null}
      </div>
    </div>
  );
}
