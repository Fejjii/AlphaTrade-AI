export type SourceCoverage = "complete" | "truncated";

/** Derive list coverage from paginated API fields. */
export function coverageFromPage(loaded: number, total: number): SourceCoverage {
  return loaded < total ? "truncated" : "complete";
}

export function documentsCoverageMessage(loaded: number, total: number): string {
  return `Only ${loaded} of ${total} knowledge documents are loaded. Library views and loaded-page search may be incomplete.`;
}
