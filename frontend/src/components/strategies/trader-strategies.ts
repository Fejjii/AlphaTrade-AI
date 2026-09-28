import type { JournalStatsBucket, StrategyCard, UserStrategy } from "@/lib/api/types";

export function rulesFromCard(card: StrategyCard | null | undefined): string[] {
  if (!card) return [];
  return [...card.invalidation, ...card.no_trade_rules, ...card.stop_loss].filter(
    (item) => item.trim().length > 0,
  );
}

export function patternsFromCard(card: StrategyCard | null | undefined): string[] {
  if (!card) return [];
  return [...card.entry_conditions, ...card.confirmation_conditions].filter(
    (item) => item.trim().length > 0,
  );
}

/** Match a journal statistics bucket only when the API key, id, or label lines up. */
export function performanceForStrategy(
  strategy: Pick<UserStrategy, "id" | "name">,
  buckets: readonly JournalStatsBucket[],
): JournalStatsBucket | null {
  return (
    buckets.find(
      (bucket) =>
        bucket.group_id === strategy.id ||
        bucket.key === strategy.id ||
        bucket.label === strategy.name,
    ) ?? null
  );
}

export function isHttpEvidenceRef(ref: string): boolean {
  return /^https?:\/\//i.test(ref.trim());
}
