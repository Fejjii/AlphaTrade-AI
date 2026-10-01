/**
 * Per-trade Agent reflections are not stored on journal entries or canonical trades.
 * Coaching prompts are a separate generated list and must not be labeled as reflections.
 */
export const AGENT_REFLECTION_CONTRACT =
  "No per-trade Agent reflection record exists. Coaching prompts are generated separately and are not stored reflections on a trade.";

export function journalMistakes(mistakes: readonly string[]): string {
  const cleaned = mistakes.map((item) => item.trim()).filter((item) => item.length > 0);
  return cleaned.length > 0 ? cleaned.join(" · ") : "—";
}
