import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RelatedStageLinks } from "@/components/validate/RelatedStageLinks";

afterEach(() => {
  cleanup();
});

describe("RelatedStageLinks", () => {
  it("links related stages when ids exist and omits current self-link", () => {
    render(
      <RelatedStageLinks
        current="candidate"
        draftId="draft-1"
        candidateId="cand-1"
        runPlanId="plan-1"
        sourceAlertId="alert-1"
      />,
    );
    expect(screen.getByRole("link", { name: "Validate hub" })).toHaveAttribute(
      "href",
      "/paper-validation",
    );
    expect(screen.getByRole("link", { name: "Related draft" })).toHaveAttribute(
      "href",
      "/paper-validation/drafts/draft-1",
    );
    expect(screen.getByRole("link", { name: "Related run plan" })).toHaveAttribute(
      "href",
      "/paper-validation/run-plans/plan-1",
    );
    expect(screen.queryByRole("link", { name: "Related candidate" })).not.toBeInTheDocument();
  });

  it("provides safe fallback messaging when related objects are missing", () => {
    render(<RelatedStageLinks current="run_session" runSessionId="sess-1" />);
    expect(screen.getByTestId("related-stage-fallback")).toHaveTextContent(/Unavailable relations/i);
    expect(screen.queryByRole("link", { name: "Related draft" })).not.toBeInTheDocument();
  });
});
