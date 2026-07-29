import { loadSource, type SourceResult } from "@/components/workflows";
import type { PaginatedPositions, Position } from "@/lib/api/types";

type ClosedListFn = (params: {
  status: "closed" | "liquidated";
  limit: number;
}) => Promise<PaginatedPositions>;

/**
 * Fetch closed and liquidated paper positions and merge them (FP2-221).
 * A single `status=closed` list cannot surface liquidated rows.
 */
export async function loadClosedPositionsSource(
  list: ClosedListFn,
): Promise<SourceResult<PaginatedPositions>> {
  const [closed, liquidated] = await Promise.all([
    loadSource(list({ status: "closed", limit: 50 })),
    loadSource(list({ status: "liquidated", limit: 50 })),
  ]);
  return mergeClosedAndLiquidatedSources(closed, liquidated);
}

export function mergeClosedAndLiquidatedSources(
  closed: SourceResult<PaginatedPositions>,
  liquidated: SourceResult<PaginatedPositions>,
): SourceResult<PaginatedPositions> {
  if (!closed.available && !liquidated.available) {
    return {
      data: null,
      available: false,
      error:
        closed.error ??
        liquidated.error ??
        "Closed paper positions are unavailable. This is not an empty trade history.",
      fallbackUsed: false,
    };
  }

  const items = [
    ...(closed.available && closed.data ? closed.data.items : []),
    ...(liquidated.available && liquidated.data ? liquidated.data.items : []),
  ].sort(compareClosedPositions);

  const total =
    (closed.available && closed.data ? closed.data.total : 0) +
    (liquidated.available && liquidated.data ? liquidated.data.total : 0);

  const partialError = partialClosedPositionsFailureMessage(closed, liquidated);

  return {
    data: {
      items,
      total,
      limit: 50,
      offset: 0,
    },
    available: true,
    error: partialError,
    fallbackUsed: Boolean(closed.fallbackUsed || liquidated.fallbackUsed),
  };
}

function partialClosedPositionsFailureMessage(
  closed: SourceResult<PaginatedPositions>,
  liquidated: SourceResult<PaginatedPositions>,
): string | null {
  const closedFailed = !closed.available;
  const liquidatedFailed = !liquidated.available;
  if (!closedFailed && !liquidatedFailed) {
    return null;
  }
  if (closedFailed && !liquidatedFailed) {
    return withSafeDetail(
      "Closed positions unavailable; showing liquidated positions only.",
      closed.error,
    );
  }
  if (liquidatedFailed && !closedFailed) {
    return withSafeDetail(
      "Liquidated positions unavailable; showing closed positions only.",
      liquidated.error,
    );
  }
  return closed.error ?? liquidated.error ?? "Closed paper positions are unavailable.";
}

function withSafeDetail(message: string, detail: string | null | undefined): string {
  const trimmed = detail?.trim();
  if (!trimmed || trimmed === message) {
    return message;
  }
  return `${message} (${trimmed})`;
}

function compareClosedPositions(a: Position, b: Position): number {
  const aKey = a.closed_at ?? a.opened_at;
  const bKey = b.closed_at ?? b.opened_at;
  return bKey.localeCompare(aKey);
}
