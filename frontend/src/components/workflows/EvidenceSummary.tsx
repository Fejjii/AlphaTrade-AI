type EvidenceSummaryProps = {
  title?: string;
  thesis?: string | null;
  items?: Array<{ label: string; value: string | null | undefined }>;
  limitations?: string[];
};

export function EvidenceSummary({
  title = "Thesis and evidence",
  thesis,
  items = [],
  limitations = [],
}: EvidenceSummaryProps) {
  return (
    <section
      aria-labelledby="evidence-summary-heading"
      data-testid="evidence-summary"
      className="rounded-control border border-border-subtle bg-surface-0/40 p-4"
    >
      <h3 id="evidence-summary-heading" className="text-sm font-semibold text-text-primary">
        {title}
      </h3>
      {thesis ? <p className="mt-2 whitespace-pre-wrap text-sm text-text-secondary">{thesis}</p> : (
        <p className="mt-2 text-sm text-text-muted">No thesis available from existing APIs.</p>
      )}
      {items.length ? (
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          {items.map((item) => (
            <div key={item.label}>
              <dt className="text-caption text-text-muted">{item.label}</dt>
              <dd className="text-text-primary">{item.value ?? "—"}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {limitations.length ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-caption text-text-muted">
          {limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
