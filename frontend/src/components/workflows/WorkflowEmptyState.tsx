import { AlertTriangle, Inbox } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type WorkflowEmptyStateProps = {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  href?: string;
  tone?: "empty" | "error";
  className?: string;
};

export function WorkflowEmptyState({
  title,
  description,
  actionLabel,
  onAction,
  tone = "empty",
  className,
}: WorkflowEmptyStateProps) {
  const Icon = tone === "error" ? AlertTriangle : Inbox;
  return (
    <div
      data-testid="workflow-empty-state"
      className={cn(
        "flex flex-col items-center justify-center rounded-card border border-dashed px-6 py-10 text-center",
        tone === "error"
          ? "border-danger-border bg-danger-muted/30"
          : "border-border bg-surface-0/40",
        className,
      )}
    >
      <Icon
        className={cn(
          "mb-3 h-8 w-8",
          tone === "error" ? "text-danger" : "text-text-disabled",
        )}
        aria-hidden="true"
      />
      <h3
        className={cn(
          "text-base font-medium",
          tone === "error" ? "text-danger" : "text-text-primary",
        )}
      >
        {title}
      </h3>
      {description ? <p className="mt-2 max-w-md text-sm text-text-muted">{description}</p> : null}
      {actionLabel && onAction ? (
        <Button type="button" variant="outline" size="sm" className="mt-4" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
