export type SourceCoverage = "complete" | "truncated";

/** Derive list coverage from paginated API fields. */
export function coverageFromPage(loaded: number, total: number): SourceCoverage {
  return loaded < total ? "truncated" : "complete";
}

export function pendingCoverageMessage(loaded: number, total: number): string {
  return `Only ${loaded} of ${total} pending lessons are loaded. The attention queue may be incomplete.`;
}

export function reviewedCoverageMessage(
  label: string,
  loaded: number,
  total: number,
): string {
  return `${label} history is truncated (${loaded} of ${total} loaded). Loaded history may not represent all reviewed lessons.`;
}
