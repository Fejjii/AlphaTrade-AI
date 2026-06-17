export function NotFinancialAdviceBanner() {
  return (
    <p
      className="rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs text-zinc-400"
      data-testid="not-financial-advice-disclaimer"
    >
      Not financial advice. AlphaTrade AI is a paper-only research and journaling tool — simulated
      results do not guarantee real-world performance.
    </p>
  );
}
