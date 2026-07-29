import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChartFrame } from "./ChartFrame";
import { SOURCE_JOURNAL_RULE_COMPLIANCE } from "./sourceLabels";

describe("ChartFrame", () => {
  afterEach(() => cleanup());
  it("shows loading skeleton without chart content", () => {
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel={SOURCE_JOURNAL_RULE_COMPLIANCE}
        loading
        data-testid="frame"
      />,
    );
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByTestId("frame-plot")).not.toBeInTheDocument();
  });

  it("shows error state with retry and no fabricated chart", () => {
    const onRetry = vi.fn();
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel={SOURCE_JOURNAL_RULE_COMPLIANCE}
        error="Source down"
        onRetry={onRetry}
        data-testid="frame"
      >
        <div data-testid="frame-plot">plot</div>
      </ChartFrame>,
    );
    expect(screen.getByTestId("frame-error")).toBeInTheDocument();
    expect(screen.queryByTestId("frame-plot")).not.toBeInTheDocument();
  });

  it("shows empty state when there is no data", () => {
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel={SOURCE_JOURNAL_RULE_COMPLIANCE}
        empty
        emptyTitle="Nothing here"
        data-testid="frame"
      >
        <div data-testid="frame-plot">plot</div>
      </ChartFrame>,
    );
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.queryByTestId("frame-plot")).not.toBeInTheDocument();
  });

  it("renders chart children when data is available", () => {
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel={SOURCE_JOURNAL_RULE_COMPLIANCE}
        data-testid="frame"
      >
        <div data-testid="frame-plot">plot</div>
      </ChartFrame>,
    );
    expect(screen.getByTestId("frame-plot")).toBeInTheDocument();
    expect(screen.getByTestId("frame-source")).toHaveTextContent(SOURCE_JOURNAL_RULE_COMPLIANCE);
  });

  it("renders formatted as-of without raw ISO microsecond stamp", () => {
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel={SOURCE_JOURNAL_RULE_COMPLIANCE}
        generatedAt="2026-07-28T16:43:30.123937Z"
        data-testid="frame"
      >
        <div>plot</div>
      </ChartFrame>,
    );

    const generated = screen.getByTestId("frame-generated-at");
    expect(generated).toHaveTextContent(/as of/i);
    expect(generated.textContent).not.toMatch(/T16:43:30\.123937Z/);
    expect(generated.textContent).not.toMatch(/2026-07-28T/);
  });

  it("shows truncated and insufficient sample notices", () => {
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel={SOURCE_JOURNAL_RULE_COMPLIANCE}
        truncated={{ maxRows: 5000 }}
        insufficientSample={{ n: 3, min: 5 }}
        data-testid="frame"
      >
        <div>plot</div>
      </ChartFrame>,
    );
    expect(screen.getByTestId("limitations-state")).toBeInTheDocument();
    expect(screen.getByTestId("frame-insufficient")).toHaveTextContent("n=3 — insufficient (min 5)");
  });
});
