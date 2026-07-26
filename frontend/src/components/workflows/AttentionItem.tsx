import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AttentionItemModel, AttentionItemTone } from "@/components/workflows/types";

const toneClass: Record<AttentionItemTone, string> = {
  default: "border-border-subtle bg-surface-0/50",
  warning: "border-warning-border bg-warning-muted/40",
  danger: "border-danger-border bg-danger-muted/40",
  info: "border-info-border bg-info-muted/40",
  success: "border-success-border bg-success-muted/30",
};

type AttentionItemProps = {
  item: AttentionItemModel;
};

export function AttentionItem({ item }: AttentionItemProps) {
  const tone = item.tone ?? "default";
  return (
    <li data-testid={`attention-item-${item.id}`}>
      <Link
        href={item.href}
        className={cn(
          "flex min-h-11 flex-col gap-1 rounded-control border px-4 py-3 transition",
          "hover:border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
          toneClass[tone],
        )}
        aria-label={`${item.actionLabel}: ${item.title}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-text-primary">{item.title}</p>
            <p className="mt-0.5 text-sm text-text-secondary">{item.summary}</p>
            {item.meta ? <p className="mt-1 text-caption text-text-muted">{item.meta}</p> : null}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            {item.count != null ? (
              <Badge variant="muted" aria-label={`${item.count} items`}>
                {item.count}
              </Badge>
            ) : null}
            <span className="text-caption font-medium text-text-primary">{item.actionLabel}</span>
          </div>
        </div>
      </Link>
    </li>
  );
}
