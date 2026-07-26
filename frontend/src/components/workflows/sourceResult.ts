export type SourceResult<T> = {
  data: T | null;
  available: boolean;
  error: string | null;
  fallbackUsed: boolean;
};

export type NamedSourceResult<T> = SourceResult<T> & {
  name: string;
  required?: boolean;
};

export function okSource<T>(data: T, options?: { fallbackUsed?: boolean }): SourceResult<T> {
  return {
    data,
    available: true,
    error: null,
    fallbackUsed: options?.fallbackUsed ?? false,
  };
}

export function failedSource<T>(error: unknown, fallbackUsed = false): SourceResult<T> {
  return {
    data: null,
    available: false,
    error: error instanceof Error ? error.message : "Request failed",
    fallbackUsed,
  };
}

/** Load a source without converting failures into fake empty success data. */
export async function loadSource<T>(promise: Promise<T>): Promise<SourceResult<T>> {
  try {
    return okSource(await promise);
  } catch (error) {
    return failedSource<T>(error);
  }
}

export function unavailableSourceNames(
  sources: Array<{ name: string; available: boolean; required?: boolean }>,
  options?: { requiredOnly?: boolean },
): string[] {
  return sources
    .filter((source) => !source.available && (!options?.requiredOnly || source.required))
    .map((source) => source.name);
}

export function anySourceFailed(
  sources: Array<{ available: boolean; required?: boolean }>,
  options?: { requiredOnly?: boolean },
): boolean {
  return sources.some(
    (source) => !source.available && (!options?.requiredOnly || source.required),
  );
}

export function allSourcesAvailable(
  sources: Array<{ available: boolean }>,
): boolean {
  return sources.every((source) => source.available);
}
