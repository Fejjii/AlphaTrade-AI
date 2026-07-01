"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ValidationActionLabel, ValidationPriorityItem } from "@/lib/api/types";

import { validationPriorityItemHref } from "./priority-display";

const ACTION_META: Record<
  ValidationActionLabel,
  { label: string; tone: "info" | "warn" | "blocked" | "muted" }
> = {
  prioritize: { label: "Prioritize", tone: "info" },
  watch: { label: "Watch", tone: "muted" },
  collect_more_data: { label: "Collect more data", tone: "warn" },
  avoid_for_now: { label: "Avoid for now", tone: "blocked" },
};

export function PriorityItemCard({ item }: { item: ValidationPriorityItem }) {
  const action = ACTION_META[item.action_label];
  const title = item.condition || item.symbol || item.item_type;
  const detailHref = validationPriorityItemHref(item);
  const detailLabel =
    item.item_type === "run_plan" ? "Open run plan" : "Open candidate";
  return (
    <Card data-testid={`validation-priority-item-${item.item_id}`}>
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="text-base">
            <Link
              href={detailHref}
              className="hover:underline"
              data-testid={`validation-priority-item-link-${item.item_id}`}
            >
              {title}
            </Link>
          </CardTitle>
          <p className="mt-1 text-xs text-zinc-500">
            {item.item_type} · {item.symbol ?? "—"} · {item.timeframe ?? "—"} ·{" "}
            {item.direction ?? "—"}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <StatusBadge label={action.label} tone={action.tone} />
          <span className="text-xs text-zinc-500" data-testid="validation-priority-score">
            score {item.priority_score}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p className="text-xs text-zinc-500">
          Evidence: {item.reliability} (matched {item.matched_dimension} &quot;
          {item.matched_key}&quot;, n={item.matched_sample_size})
        </p>

        {item.rationale.length ? (
          <ul className="list-disc space-y-1 pl-5">
            {item.rationale.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}

        {item.factors.length ? (
          <div>
            <p className="mb-1 text-xs font-medium text-zinc-400">Why</p>
            <ul className="space-y-1">
              {item.factors.map((factor) => (
                <li
                  key={factor.code}
                  data-testid={`validation-priority-factor-${factor.code}`}
                  className="flex items-start justify-between gap-2 text-xs"
                >
                  <span className="text-zinc-300">{factor.detail}</span>
                  <span
                    className={
                      factor.direction === "negative"
                        ? "text-red-400"
                        : factor.direction === "positive"
                          ? "text-emerald-400"
                          : "text-zinc-500"
                    }
                  >
                    {factor.contribution > 0 ? `+${factor.contribution}` : factor.contribution}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <Link
          href={detailHref}
          className="inline-block text-xs text-zinc-400 underline"
          data-testid={`validation-priority-detail-link-${item.item_id}`}
        >
          {detailLabel}
        </Link>
      </CardContent>
    </Card>
  );
}
