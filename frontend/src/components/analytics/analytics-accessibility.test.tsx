import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnalyticsFilterBar } from "@/components/analytics/AnalyticsFilterBar";
import { ComparisonChart } from "@/components/analytics/ComparisonChart";
import { RuleComplianceChart } from "@/components/analytics/RuleComplianceChart";
import { SetupBucketTable } from "@/components/analytics/SetupBucketTable";
import { SetupGroupToggle } from "@/components/analytics/SetupGroupToggle";
import type {
  AnalyticsFilterState,
  DatePreset,
} from "@/components/analytics/useAnalyticsFilters";
import type { SourceResult } from "@/components/workflows";
import type {
  JournalComparisonResponse,
  JournalStatsResponse,
  JournalTradeStatsMetrics,
} from "@/lib/api/types";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  Cell: () => null,
}));

const PRESET_IDS: DatePreset[] = ["7d", "30d", "90d", "ytd", "all"];

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function metrics(overrides: Partial<JournalTradeStatsMetrics> = {}): JournalTradeStatsMetrics {
  return {
    trade_count: 4,
    wins: 2,
    losses: 2,
    breakeven: 0,
    win_rate: 0.5,
    pnl_sample_count: 4,
    net_pnl_total: "10",
    gross_pnl_total: "20",
    expectancy: "2.5",
    average_winner: "10",
    average_loser: "-5",
    profit_factor: 2,
    r_sample_count: 0,
    average_r: null,
    cost_sample_count: 0,
    fees_total: "0",
    funding_total: "0",
    slippage_total: "0",
    total_costs: "0",
    mfe_sample_count: 0,
    average_mfe_amount: null,
    mae_sample_count: 0,
    average_mae_amount: null,
    capture_sample_count: 0,
    available_profit_total: null,
    realized_on_available_total: null,
    average_realized_vs_available_pct: null,
    confidence: "moderate",
    warnings: [],
    ...overrides,
  };
}

const journalBuckets: JournalStatsResponse = {
  group_by: "setup",
  filters: {},
  overall: metrics({ trade_count: 12 }),
  buckets: [
    {
      key: "setup-a",
      group_id: "setup-a",
      label: "Alpha",
      metrics: metrics(),
    },
  ],
  total_buckets: 45,
  limit: 20,
  offset: 0,
  truncated: false,
  max_rows: 5000,
  generated_at: "2026-07-25T12:00:00Z",
};

const ruleCompliance: JournalStatsResponse = {
  ...journalBuckets,
  group_by: "rule_compliance",
  buckets: [
    {
      key: "compliant",
      group_id: "compliant",
      label: "Compliant",
      metrics: metrics({ trade_count: 6 }),
    },
  ],
  total_buckets: 1,
};

const comparison: JournalComparisonResponse = {
  filters: {},
  cohorts: [
    { cohort: "human", sample_count: 4, truncated: false, metrics: metrics() },
    { cohort: "paper_system", sample_count: 4, truncated: false, metrics: metrics() },
  ],
  scorecards: [],
  by_entry_method: [],
  by_source: [],
  rule_compliance: [],
  decision_quality: {
    timing_sample_count: 0,
    average_entry_timing_pct: null,
    early_exit_sample_count: 0,
    early_exit_count: null,
    early_exit_rate: null,
    missed_profit_sample_count: 0,
    average_missed_profit: null,
    average_capture_pct: null,
    warnings: [],
  },
  breakdowns: [],
  links: {
    journal_trades_path: "/journal",
    journal_statistics_path: "/journal/statistics",
    journal_comparison_path: "/journal/comparison",
    backtests_path: "/strategy-lab",
    research_validation_path: "/research-validation",
    paper_validation_candidates_path: "/paper-validation/candidates",
  },
  confidence: "moderate",
  warnings: [],
  generated_at: "2026-07-25T12:00:00Z",
  max_rows: 5000,
  note: "",
};

function filterState(overrides: Partial<AnalyticsFilterState> = {}): AnalyticsFilterState {
  return {
    tab: "overview",
    dateFrom: null,
    dateTo: null,
    symbol: null,
    timeframe: null,
    portfolioSource: "all",
    journalSource: null,
    setupId: null,
    userStrategyId: null,
    ruleCompliance: null,
    marketRegime: null,
    minSample: 5,
    dimension: "session",
    groupBy: "setup",
    bucketOffset: 0,
    ignoredParams: [],
    ...overrides,
  } as AnalyticsFilterState;
}

function renderFilterBar(state = filterState()) {
  return render(
    <AnalyticsFilterBar
      state={state}
      onApplyDraft={vi.fn()}
      onApplyPreset={vi.fn()}
      onClear={vi.fn()}
    />,
  );
}

describe("Analytics filter bar mobile disclosure (FP2-219)", () => {
  afterEach(() => cleanup());

  it("collapses the controls behind a disclosure below the lg breakpoint", () => {
    renderFilterBar();
    const toggle = screen.getByTestId("analytics-filters-disclosure");
    const controls = screen.getByTestId("analytics-filter-controls");

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls", controls.id);
    expect(toggle).toHaveTextContent("Show filters");
    expect(controls.className).toContain("hidden");
    expect(controls.className).toContain("lg:block");
    expect(toggle.className).toContain("lg:hidden");
  });

  it("expands the controls on demand", () => {
    renderFilterBar();
    const toggle = screen.getByTestId("analytics-filters-disclosure");
    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveTextContent("Hide filters");
    expect(screen.getByTestId("analytics-filter-controls").className).not.toContain("hidden");
  });

  it("keeps the applied-filter summary visible while collapsed", () => {
    renderFilterBar();
    const summary = screen.getByTestId("analytics-filter-summary");
    expect(summary).toBeInTheDocument();
    expect(screen.getByTestId("analytics-filter-controls").contains(summary)).toBe(false);
  });
});

describe("Analytics touch targets (FP2-216)", () => {
  afterEach(() => cleanup());

  it("gives the disclosure and every preset a 44 px touch target", () => {
    renderFilterBar();
    expect(screen.getByTestId("analytics-filters-disclosure").className).toContain("min-h-11");
    for (const preset of PRESET_IDS) {
      expect(screen.getByTestId(`analytics-preset-${preset}`).className).toContain("min-h-11");
    }
  });

  it("gives rule-compliance metric toggles a 44 px touch target", () => {
    render(<RuleComplianceChart source={ok(ruleCompliance)} />);
    const group = screen.getByTestId("rule-compliance-metric-toggle");
    for (const button of within(group).getAllByRole("button")) {
      expect(button.className).toContain("min-h-11");
    }
  });

  it("gives comparison metric toggles a 44 px touch target", () => {
    render(<ComparisonChart source={ok(comparison)} />);
    const group = screen.getByTestId("comparison-metric-toggle");
    for (const button of within(group).getAllByRole("button")) {
      expect(button.className).toContain("min-h-11");
    }
  });

  it("gives setup-bucket pagination a 44 px touch target", () => {
    render(
      <SetupBucketTable
        source={ok(journalBuckets)}
        groupBy="setup"
        bucketOffset={0}
        onPageChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("setup-bucket-prev").className).toContain("min-h-11");
    expect(screen.getByTestId("setup-bucket-next").className).toContain("min-h-11");
  });
});

describe("SetupGroupToggle roving tabindex (FP2-217)", () => {
  afterEach(() => cleanup());

  it("exposes exactly one tab stop for the radio group", () => {
    render(<SetupGroupToggle value="setup" onChange={vi.fn()} />);
    const radios = screen.getAllByRole("radio");
    expect(radios.filter((radio) => radio.getAttribute("tabindex") === "0")).toHaveLength(1);
    expect(screen.getByTestId("setup-group-setup")).toHaveAttribute("tabindex", "0");
    expect(screen.getByTestId("setup-group-strategy")).toHaveAttribute("tabindex", "-1");
  });

  it("moves selection with arrow keys and wraps", () => {
    const onChange = vi.fn();
    render(<SetupGroupToggle value="setup" onChange={onChange} />);
    fireEvent.keyDown(screen.getByTestId("setup-group-setup"), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("setup_version");

    onChange.mockClear();
    fireEvent.keyDown(screen.getByTestId("setup-group-setup"), { key: "ArrowLeft" });
    expect(onChange).toHaveBeenCalledWith("strategy");
  });

  it("jumps to the first and last option with Home and End", () => {
    const onChange = vi.fn();
    render(<SetupGroupToggle value="setup_version" onChange={onChange} />);
    fireEvent.keyDown(screen.getByTestId("setup-group-setup_version"), { key: "End" });
    expect(onChange).toHaveBeenCalledWith("strategy");

    onChange.mockClear();
    fireEvent.keyDown(screen.getByTestId("setup-group-setup_version"), { key: "Home" });
    expect(onChange).toHaveBeenCalledWith("setup");
  });

  it("holds a 44 px touch target on every option", () => {
    render(<SetupGroupToggle value="setup" onChange={vi.fn()} />);
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio.className).toContain("min-h-11");
    }
  });
});

describe("Analytics table header scope (FP2-217)", () => {
  afterEach(() => cleanup());

  it("scopes every column header in SetupBucketTable", () => {
    render(
      <SetupBucketTable
        source={ok(journalBuckets)}
        groupBy="setup"
        bucketOffset={0}
        onPageChange={vi.fn()}
      />,
    );
    for (const header of screen.getAllByRole("columnheader")) {
      expect(header).toHaveAttribute("scope", "col");
    }
  });
});
