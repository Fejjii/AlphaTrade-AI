/**
 * Shared, consistent safety disclaimers used across trader-facing pages.
 * Wording is intentionally calm and non-judgmental.
 */

export const SAFETY_DISCLAIMERS = [
  "Not financial advice.",
  "Paper trading only — no real orders are placed.",
  "Real trading is disabled.",
  "Alerts do not execute trades.",
  "Paper validation trades are simulated, not real orders.",
  "AI explanations never override deterministic risk rules.",
] as const;

export function SafetyDisclaimers({ className }: { className?: string }) {
  return (
    <ul
      className={`space-y-1 text-xs text-zinc-500 ${className ?? ""}`}
      data-testid="safety-disclaimers"
    >
      {SAFETY_DISCLAIMERS.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}
