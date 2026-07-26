import type {
  PaperValidationSessionObservationItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";
import { failedSource, okSource, type SourceResult } from "@/components/workflows/sourceResult";

/**
 * Outcome GET semantics:
 * - 200 + body → recorded outcome
 * - 404 NotFoundError("Session result not found.") → confirmed not recorded
 * - any other failure → source unavailable (never treat as not recorded)
 */
export type SessionResultLoad = SourceResult<PaperValidationSessionResultItem> & {
  resultNotRecorded: boolean;
};

export type RecentResultLoad = SessionResultLoad & {
  sessionId: string;
};

export function isSessionResultNotFound(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const status = (error as { status?: unknown }).status;
  return status === 404;
}

export async function loadSessionResultSource(
  promise: Promise<PaperValidationSessionResultItem>,
): Promise<SessionResultLoad> {
  try {
    return { ...okSource(await promise), resultNotRecorded: false };
  } catch (error) {
    if (isSessionResultNotFound(error)) {
      return {
        data: null,
        available: true,
        error: null,
        fallbackUsed: false,
        resultNotRecorded: true,
      };
    }
    return { ...failedSource<PaperValidationSessionResultItem>(error), resultNotRecorded: false };
  }
}

export async function loadObservationsSource(
  promise: Promise<{
    items: PaperValidationSessionObservationItem[];
    total: number;
    limit: number;
    offset: number;
  }>,
): Promise<SourceResult<PaperValidationSessionObservationItem[]>> {
  try {
    const list = await promise;
    return okSource(list.items);
  } catch (error) {
    return failedSource<PaperValidationSessionObservationItem[]>(error);
  }
}

export async function loadRecentSessionResults(
  sessions: Array<{ session_id: string; session_status: string }>,
  fetchResult: (sessionId: string) => Promise<PaperValidationSessionResultItem>,
  limit = 5,
): Promise<RecentResultLoad[]> {
  const completed = sessions
    .filter((session) => session.session_status === "completed")
    .slice(0, limit);
  return Promise.all(
    completed.map(async (session) => ({
      sessionId: session.session_id,
      ...(await loadSessionResultSource(fetchResult(session.session_id))),
    })),
  );
}

export type OutcomeCoverage = {
  completedSessionsProbed: number;
  resultsLoaded: number;
  resultsUnavailable: number;
  resultsNotRecorded: number;
};

export function summarizeOutcomeCoverage(recentResults: RecentResultLoad[]): OutcomeCoverage {
  let resultsLoaded = 0;
  let resultsUnavailable = 0;
  let resultsNotRecorded = 0;
  for (const result of recentResults) {
    if (!result.available) {
      resultsUnavailable += 1;
    } else if (result.resultNotRecorded || result.data == null) {
      resultsNotRecorded += 1;
    } else {
      resultsLoaded += 1;
    }
  }
  return {
    completedSessionsProbed: recentResults.length,
    resultsLoaded,
    resultsUnavailable,
    resultsNotRecorded,
  };
}
