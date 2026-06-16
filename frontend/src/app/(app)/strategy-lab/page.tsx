"use client";

import Link from "next/link";
import { useCallback } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { SETUP_TYPE_OPTIONS } from "@/lib/setup-types";

function setupLabel(value: string) {
  return SETUP_TYPE_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

export default function StrategyLabPage() {
  const loader = useCallback(() => api.strategies.list(), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Strategy Lab</h1>
        <p className="text-sm text-zinc-400">
          Build and version strategy cards for paper-only pre-trade workflows.
        </p>
      </div>

      {loading ? <LoadingState label="Loading strategies…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data?.items.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {data.items.map((strategy) => (
            <Link key={strategy.id} href={`/strategy-lab/${strategy.id}`}>
              <Card className="transition hover:border-zinc-600">
                <CardHeader>
                  <CardTitle className="text-base">{strategy.name}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-sm text-zinc-300">
                  <p>Setup: {setupLabel(strategy.setup_type)}</p>
                  <p>Version: {strategy.current_version}</p>
                  <p>Status: {strategy.validation_status ?? "draft"}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : null}

      {data && !data.items.length ? (
        <EmptyState
          title="No strategies yet"
          description="Create a strategy card from the AI Workspace or API to populate the library."
        />
      ) : null}
    </div>
  );
}
