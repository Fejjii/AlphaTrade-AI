import type { ValidateFunction } from "ajv";
import { apiFetch, ApiError } from "./client";

type Options = Parameters<typeof apiFetch>[1] & {
  bodyValue?: unknown;
  requestValidator?: ValidateFunction;
  responseValidator: ValidateFunction;
};

/** Validation uses generated schemas; the existing authenticated transport owns I/O. */
export async function validatedFetch<T>(path: string, options: Options): Promise<T> {
  const { bodyValue, requestValidator, responseValidator, ...transport } = options;
  if (requestValidator && !requestValidator(bodyValue)) {
    throw new ApiError("Invalid API request. Check the supplied fields.", 0, null);
  }
  const result = await apiFetch<unknown>(path, {
    ...transport,
    ...(requestValidator ? { body: JSON.stringify(bodyValue) } : {}),
  });
  if (!responseValidator(result)) {
    // Never include rejected payloads or validation data in user-visible errors/logs.
    throw new ApiError("API response did not match its contract. Refresh or try again later.", 0, null);
  }
  return result as T; // Narrowing occurs only after generated runtime validation.
}
