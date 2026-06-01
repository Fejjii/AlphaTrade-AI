import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import type { ProviderStatus } from "@/lib/api/types";

function providerLabel(provider: ProviderStatus): string {
  if (provider.is_mock) return "Mock";
  if (provider.using_fallback) return "Fallback";
  return "Live";
}

function providerTone(provider: ProviderStatus): "paper" | "warn" | "healthy" | "muted" {
  if (provider.is_mock || provider.using_fallback) return "paper";
  if (provider.health === "healthy") return "healthy";
  if (provider.health === "degraded") return "warn";
  return "muted";
}

export function ProviderStatusCard({ provider }: { provider: ProviderStatus }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm">{provider.name}</CardTitle>
          <StatusBadge label={providerLabel(provider)} tone={providerTone(provider)} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-zinc-400">
        <div className="flex flex-wrap gap-2">
          <StatusBadge label={provider.kind} tone="muted" />
          <StatusBadge label={provider.health} tone={provider.health} />
          {provider.using_fallback ? <StatusBadge label="Using fallback" tone="warn" /> : null}
          {!provider.is_mock && !provider.using_fallback ? (
            <StatusBadge label="Configured" tone="healthy" />
          ) : null}
        </div>
        {provider.detail ? <p>{provider.detail}</p> : null}
        {provider.last_success_at ? (
          <p className="text-xs">Last success: {new Date(provider.last_success_at).toLocaleString()}</p>
        ) : null}
        {provider.error_message ? (
          <p className="text-xs text-amber-400">Error: {provider.error_message}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
