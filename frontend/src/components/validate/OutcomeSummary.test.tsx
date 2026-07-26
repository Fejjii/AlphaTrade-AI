import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { OutcomeSummary } from "@/components/validate/OutcomeSummary";

afterEach(() => {
  cleanup();
});

describe("OutcomeSummary", () => {
  it("shows high-level observation and outcome summary with progressive disclosure", () => {
    render(
      <OutcomeSummary
        observationsAvailable
        observations={[
          {
            observation_id: "obs-1",
            run_session_id: "sess-1",
            run_plan_id: "plan-1",
            observation_kind: "hit_trigger",
            observed_price: 65000,
            observed_at: "2026-07-26T13:30:00.000Z",
            note: "Touched trigger",
            created_at: "2026-07-26T13:30:00.000Z",
          },
        ]}
        resultAvailable
        result={{
          result_id: "res-1",
          run_session_id: "sess-1",
          run_plan_id: "plan-1",
          outcome: "success",
          success_criteria_met: "met",
          failure_criteria_met: "not_met",
          invalidation_hit: false,
          entry_assessment: "entered_as_planned",
          discipline_assessment: "disciplined",
          lessons: "Wait for confirmation",
          recorded_at: "2026-07-26T14:00:00.000Z",
          created_at: "2026-07-26T14:00:00.000Z",
        }}
      />,
    );

    expect(screen.getByTestId("outcome-observation-count")).toHaveTextContent("1");
    expect(screen.getByTestId("outcome-latest-observation")).toHaveTextContent(/hit trigger/i);
    expect(screen.getByTestId("outcome-mfe")).toHaveTextContent(/unavailable/i);
    expect(screen.getByTestId("outcome-mae")).toHaveTextContent(/unavailable/i);
    expect(screen.getByTestId("outcome-discipline")).toHaveTextContent(/disciplined/i);
    expect(screen.getByTestId("outcome-details")).not.toBeVisible();

    fireEvent.click(screen.getByTestId("outcome-toggle-details"));
    expect(screen.getByTestId("outcome-details")).toBeVisible();
    expect(screen.getByTestId("outcome-obs-obs-1")).toHaveTextContent(/Touched trigger/);
    expect(screen.getByText(/Wait for confirmation/)).toBeInTheDocument();
  });

  it("keeps unavailable observation/result states honest", () => {
    render(
      <OutcomeSummary
        observations={null}
        observationsAvailable={false}
        result={null}
        resultAvailable={false}
        resultError="down"
      />,
    );
    expect(screen.getByTestId("outcome-obs-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-result-unavailable")).toHaveTextContent(/down/);
    expect(screen.getByTestId("outcome-observation-count")).toHaveTextContent("unavailable");
  });
});
