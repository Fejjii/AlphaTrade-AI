import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WorkflowStepper } from "@/components/WorkflowStepper";
import { buildWorkflowSteps } from "@/lib/workflow-steps";

afterEach(cleanup);

describe("WorkflowStepper", () => {
  it("renders all six workflow steps", () => {
    render(<WorkflowStepper steps={buildWorkflowSteps({ strategyId: "s1" })} />);
    expect(screen.getByTestId("workflow-stepper")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-idea")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-structure")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-backtest")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-paper_validate")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-review_lessons")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-improve_strategy")).toBeInTheDocument();
  });

  it("highlights the next action for the focus step", () => {
    render(<WorkflowStepper steps={buildWorkflowSteps({ strategyId: "s1" })} />);
    expect(screen.getByTestId("workflow-next-action")).toHaveTextContent("structured");
  });
});
