import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChartFrame } from "./ChartFrame";

describe("ChartFrame", () => {
  afterEach(() => cleanup());
  it("shows loading skeleton without chart content", () => {
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel="GET /example"
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
        sourceLabel="GET /example"
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
        sourceLabel="GET /example"
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
      <ChartFrame title="Test chart" sourceLabel="GET /example" data-testid="frame">
        <div data-testid="frame-plot">plot</div>
      </ChartFrame>,
    );
    expect(screen.getByTestId("frame-plot")).toBeInTheDocument();
    expect(screen.getByTestId("frame-source")).toHaveTextContent("GET /example");
  });

  it("shows truncated and insufficient sample notices", () => {
    render(
      <ChartFrame
        title="Test chart"
        sourceLabel="GET /example"
        truncated={{ maxRows: 5000 }}
        insufficientSample={{ n: 3, min: 5 }}
        data-testid="frame"
      >
        <div>plot</div>
      </ChartFrame>,
    );
    expect(screen.getByTestId("limitations-state")).toBeInTheDocument();
    expect(screen.getByTestId("frame-insufficient")).toHaveTextContent(/insufficient/i);
  });
});
