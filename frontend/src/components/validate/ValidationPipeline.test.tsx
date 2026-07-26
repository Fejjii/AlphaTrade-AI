import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ValidationPipeline } from "@/components/validate/ValidationPipeline";
import { VALIDATION_STAGE_ORDER, type ValidationStageModel } from "@/components/validate/types";
import { RiskBlock } from "@/components/ui/risk-block";

afterEach(() => {
  cleanup();
});

function stage(id: ValidationStageModel["id"], index: number): ValidationStageModel {
  return {
    id,
    name: id.replaceAll("_", " "),
    purpose: `Purpose ${index}`,
    href: "/paper-validation",
    count: index,
    statusLabel: "ok",
    nextAction: "Continue",
    blocker: null,
    timestamp: "2026-07-26T10:00:00.000Z",
    available: true,
    renderable: true,
    fullyAvailable: true,
    coverageStatus: null,
    errorCount: 0,
    sourceName: id,
  };
}

describe("ValidationPipeline Phase C2", () => {
  it("renders a vertical ordered pipeline suitable for 390px layouts", () => {
    const stages = VALIDATION_STAGE_ORDER.map((id, index) => stage(id, index));
    render(
      <div style={{ width: 390 }}>
        <ValidationPipeline stages={stages} />
      </div>,
    );

    const list = screen.getByTestId("validation-pipeline-stages");
    expect(list.tagName).toBe("OL");
    expect(list.className).toMatch(/flex/);
    expect(list.className).toMatch(/flex-col/);
    expect(list.children).toHaveLength(6);
    // Mobile-first vertical stack: no wide table forced into the 390px viewport.
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByTestId("validation-stage-draft")).toBeInTheDocument();
    expect(screen.getByTestId("validation-stage-link-outcome")).toHaveAttribute(
      "href",
      "/paper-validation",
    );
  });

  it("keeps Risk BLOCK final with no override control", () => {
    render(
      <RiskBlock reason="Daily loss lock is active." ruleReference="daily_loss_lock" />,
    );
    expect(screen.getByTestId("risk-block")).toBeInTheDocument();
    expect(screen.getByText(/No override is available/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /override/i })).not.toBeInTheDocument();
  });
});
