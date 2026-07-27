type SearchParamsLike = { get: (key: string) => string | null };

export type LessonsQueryContext = {
  candidateId: string | null;
  sourceFilter: "all" | "coaching";
};

/** Parse typed lessons deep-link and filter query parameters. */
export function parseLessonsQuery(searchParams: SearchParamsLike): LessonsQueryContext {
  return {
    candidateId: searchParams.get("candidate"),
    sourceFilter: searchParams.get("source") === "coaching" ? "coaching" : "all",
  };
}

export function lessonsCandidateHref(candidateId: string): string {
  return `/lessons?candidate=${encodeURIComponent(candidateId)}`;
}
