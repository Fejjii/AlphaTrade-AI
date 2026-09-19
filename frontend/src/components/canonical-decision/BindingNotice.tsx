import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DECISION_BACKEND_BINDINGS,
  type BackendBinding,
} from "@/lib/canonical-decision/bindings";

function tone(status: BackendBinding["status"]): "success" | "warning" | "danger" {
  if (status === "bound") return "success";
  if (status === "partial") return "warning";
  return "danger";
}

export function BindingNotice({ compact = false }: { compact?: boolean }) {
  const items = compact
    ? DECISION_BACKEND_BINDINGS.filter((item) => item.status !== "bound")
    : [...DECISION_BACKEND_BINDINGS];
  return (
    <Card data-testid="decision-binding-notice">
      <CardHeader>
        <CardTitle>Backend authority</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-text-secondary">
          This UI does not invent Candidate, ActionEligibility, or ExecutionReceipt authority.
          Missing HTTP routes are typed frontend contracts until a backend slice binds them.
        </p>
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.id} className="rounded-control border border-border-subtle p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-text-primary">{item.title}</p>
                <Badge variant={tone(item.status)} data-testid={`binding-${item.id}`}>
                  {item.status}
                </Badge>
              </div>
              <p className="mt-1 font-data text-caption text-text-muted">{item.path}</p>
              <p className="mt-1 text-caption text-text-secondary">{item.notes}</p>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
