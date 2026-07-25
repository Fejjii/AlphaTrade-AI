import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface PaperModeIndicatorProps {
  active?: boolean;
  className?: string;
  compact?: boolean;
}

/**
 * Compact persistent paper-mode chip for shell/header.
 * Does not claim paper mode from build-time config — caller passes verified state.
 */
export function PaperModeIndicator({
  active = true,
  className,
  compact = true,
}: PaperModeIndicatorProps) {
  if (!active) {
    return (
      <Badge
        variant="blocked"
        className={cn(className)}
        data-testid="paper-mode-indicator"
        aria-label="Paper mode not confirmed"
      >
        <FileText className="h-3 w-3" aria-hidden="true" />
        <span>{compact ? "Not paper" : "Paper mode not confirmed"}</span>
      </Badge>
    );
  }

  return (
    <Badge
      variant="paper"
      className={cn(className)}
      data-testid="paper-mode-indicator"
      aria-label="Paper mode active"
    >
      <FileText className="h-3 w-3" aria-hidden="true" />
      <span>{compact ? "Paper" : "Paper mode active"}</span>
    </Badge>
  );
}
