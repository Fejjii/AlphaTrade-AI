import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  ShellFreshnessProvider,
  useShellFreshness,
} from "@/contexts/ShellFreshnessContext";
import { WorkflowFreshnessAdapter } from "@/components/workflows/WorkflowFreshnessAdapter";
import { FreshnessPill } from "@/components/ui/freshness-pill";

afterEach(cleanup);

function FreshnessProbe() {
  const { freshness, setFreshness, clearFreshness } = useShellFreshness();
  return (
    <div>
      <span data-testid="probe-state">{freshness.state ?? "null"}</span>
      <span data-testid="probe-age">{freshness.ageLabel ?? ""}</span>
      {freshness.state ? (
        <FreshnessPill state={freshness.state} ageLabel={freshness.ageLabel} />
      ) : (
        <span>Freshness unavailable</span>
      )}
      <button
        type="button"
        onClick={() => setFreshness({ state: "live", ageLabel: "1m" })}
      >
        Set live
      </button>
      <button type="button" onClick={() => clearFreshness()}>
        Clear
      </button>
    </div>
  );
}

describe("ShellFreshnessContext", () => {
  it("defaults to unavailable and supports set/clear", () => {
    render(
      <ShellFreshnessProvider>
        <FreshnessProbe />
      </ShellFreshnessProvider>,
    );
    expect(screen.getByTestId("probe-state")).toHaveTextContent("null");
    expect(screen.getByText("Freshness unavailable")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Set live" }));
    expect(screen.getByTestId("probe-state")).toHaveTextContent("live");
    expect(screen.getByTestId("freshness-pill")).toHaveTextContent("Live");

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByTestId("probe-state")).toHaveTextContent("null");
  });

  it("wires honest timestamps through WorkflowFreshnessAdapter only", () => {
    render(
      <ShellFreshnessProvider>
        <WorkflowFreshnessAdapter
          timestamps={["2026-07-26T11:59:00.000Z"]}
          clearOnUnmount={false}
        />
        <FreshnessProbe />
      </ShellFreshnessProvider>,
    );
    expect(screen.getByTestId("probe-state").textContent).not.toBe("null");
  });

  it("keeps freshness unavailable when no timestamp exists", () => {
    render(
      <ShellFreshnessProvider>
        <WorkflowFreshnessAdapter timestamps={[null, undefined]} clearOnUnmount={false} />
        <FreshnessProbe />
      </ShellFreshnessProvider>,
    );
    expect(screen.getByTestId("probe-state")).toHaveTextContent("null");
  });
});
