import { Inbox } from "lucide-react";

import { cn } from "@/lib/utils";

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 px-6 py-12 text-center">
      <Inbox className="mb-3 h-8 w-8 text-zinc-600" />
      <h3 className="text-base font-medium text-zinc-200">{title}</h3>
      {description ? <p className="mt-2 max-w-md text-sm text-zinc-500">{description}</p> : null}
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center rounded-xl border border-zinc-800 bg-zinc-950/40 px-6 py-12 text-sm text-zinc-400">
      {label}
    </div>
  );
}

export function SuccessState({ message, className }: { message: string; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-6 py-4 text-center text-sm text-emerald-200",
        className,
      )}
    >
      {message}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-red-500/20 bg-red-500/5 px-6 py-8 text-center",
        className,
      )}
    >
      <p className="text-sm text-red-300">{message}</p>
      {onRetry ? (
        <button
          type="button"
          className="mt-3 text-sm text-red-200 underline"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
