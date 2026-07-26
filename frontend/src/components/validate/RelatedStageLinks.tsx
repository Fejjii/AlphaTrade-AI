import Link from "next/link";

import {
  candidateDetailHref,
  draftDetailHref,
  relatedObjectAvailable,
  runPlanDetailHref,
  runSessionDetailHref,
  sourceAlertHref,
  validateHubHref,
} from "@/components/validate/validationLinks";

type RelatedStageLinksProps = {
  draftId?: string | null;
  candidateId?: string | null;
  runPlanId?: string | null;
  runSessionId?: string | null;
  sourceAlertId?: string | null;
  /** Current page kind — omit self-link to avoid redirect loops. */
  current?: "draft" | "candidate" | "run_plan" | "run_session" | "hub";
};

export function RelatedStageLinks({
  draftId = null,
  candidateId = null,
  runPlanId = null,
  runSessionId = null,
  sourceAlertId = null,
  current,
}: RelatedStageLinksProps) {
  const links: Array<{ label: string; href: string; available: boolean }> = [
    { label: "Validate hub", href: validateHubHref(), available: current !== "hub" },
    {
      label: "Related draft",
      href: draftDetailHref(draftId),
      available: current !== "draft" && relatedObjectAvailable(draftId),
    },
    {
      label: "Related candidate",
      href: candidateDetailHref(candidateId),
      available: current !== "candidate" && relatedObjectAvailable(candidateId),
    },
    {
      label: "Related run plan",
      href: runPlanDetailHref(runPlanId),
      available: current !== "run_plan" && relatedObjectAvailable(runPlanId),
    },
    {
      label: "Related run session",
      href: runSessionDetailHref(runSessionId),
      available: current !== "run_session" && relatedObjectAvailable(runSessionId),
    },
    {
      label: "Source alert",
      href: sourceAlertHref(sourceAlertId),
      available: relatedObjectAvailable(sourceAlertId),
    },
  ];

  const visible = links.filter((link) => link.available);
  const missing = [
    current !== "draft" && !relatedObjectAvailable(draftId) ? "draft" : null,
    current !== "candidate" && !relatedObjectAvailable(candidateId) ? "candidate" : null,
    current !== "run_plan" && !relatedObjectAvailable(runPlanId) ? "run plan" : null,
    current !== "run_session" && !relatedObjectAvailable(runSessionId) ? "run session" : null,
  ].filter((item): item is string => Boolean(item));

  return (
    <nav
      aria-label="Related validation stages"
      data-testid="related-stage-links"
      className="flex flex-wrap gap-3 text-sm"
    >
      {visible.map((link) => (
        <Link
          key={link.label}
          href={link.href}
          className="inline-flex min-h-11 items-center text-text-secondary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {link.label}
        </Link>
      ))}
      {missing.length ? (
        <span className="inline-flex min-h-11 items-center text-caption text-text-muted" data-testid="related-stage-fallback">
          Unavailable relations fall back to list routes: {missing.join(", ")}.
        </span>
      ) : null}
    </nav>
  );
}
