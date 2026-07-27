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

/** All-sources filter link, optionally preserving a deep-link candidate. */
export function lessonsAllSourcesHref(candidateId?: string | null): string {
  if (candidateId) {
    return `/lessons?candidate=${encodeURIComponent(candidateId)}`;
  }
  return "/lessons";
}

/** Coaching filter link, optionally preserving a deep-link candidate. */
export function lessonsCoachingFilterHref(candidateId?: string | null): string {
  if (candidateId) {
    return `/lessons?source=coaching&candidate=${encodeURIComponent(candidateId)}`;
  }
  return "/lessons?source=coaching";
}
