import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WatcherMonitoringPanel } from "@/components/WatcherMonitoringPanel";
import { makeWatcherMonitoringSnapshot } from "@/lib/watcher-monitoring-fixtures";
import type { WatcherMonitoringSnapshot } from "@/lib/api/types";

const hookState: {
  data: WatcherMonitoringSnapshot | null;
  loading: boolean;
  error: string | null;
  reload: ReturnType<typeof vi.fn>;
} = {
  data: makeWatcherMonitoringSnapshot(),
  loading: false,
  error: null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useWatcherMonitoring", () => ({
  useWatcherMonitoring: () => hookState,
}));

afterEach(() => {
  cleanup();
  hookState.data = makeWatcherMonitoringSnapshot();
  hookState.loading = false;
  hookState.error = null;
  hookState.reload.mockReset();
});

describe("WatcherMonitoringPanel", () => {
  it("shows loading without fabricating activity", () => {
    hookState.loading = true;
    hookState.data = null;
    render(<WatcherMonitoringPanel />);
    expect(screen.getByTestId("watcher-monitoring-loading")).toHaveTextContent(
      /loading watcher monitoring/i,
    );
    expect(screen.queryByTestId("watcher-monitoring-card")).not.toBeInTheDocument();
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });

  it("shows empty when the snapshot is missing", () => {
    hookState.data = null;
    render(<WatcherMonitoringPanel />);
    expect(screen.getByTestId("watcher-monitoring-empty")).toBeInTheDocument();
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });

  it("shows error with retry", () => {
    hookState.error = "monitoring down";
    hookState.data = null;
    render(<WatcherMonitoringPanel />);
    expect(screen.getByTestId("watcher-monitoring-error")).toHaveTextContent("monitoring down");
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(hookState.reload).toHaveBeenCalled();
  });

  it("renders the stopped paper-only snapshot from the API hook", () => {
    render(<WatcherMonitoringPanel compact />);
    expect(screen.getByTestId("watcher-monitoring-card")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-monitoring-status-row")).toHaveTextContent("STOPPED");
    expect(screen.getByTestId("watcher-monitoring-paper-only")).toHaveTextContent("Paper only");
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });
});
