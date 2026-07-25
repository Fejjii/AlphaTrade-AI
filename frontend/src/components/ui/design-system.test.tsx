import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  BlockedState,
  EmptyState,
  ErrorState,
  StaleState,
  UnavailableState,
} from "@/components/states";
import { Button } from "@/components/ui/button";
import { DataNumber } from "@/components/ui/data-number";
import { FieldError, Input } from "@/components/ui/input";
import { FreshnessPill } from "@/components/ui/freshness-pill";
import { IconButton } from "@/components/ui/icon-button";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { RiskBlock } from "@/components/ui/risk-block";
import { Tabs } from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";

afterEach(() => cleanup());

describe("AT-040 design-system primitives", () => {
  it("renders PageHeader with restrained title hierarchy", () => {
    render(
      <PageHeader
        title="Dashboard"
        description="Paper workspace"
        meta={<PaperModeIndicator />}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Paper workspace")).toBeInTheDocument();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("requires accessible label on IconButton", () => {
    render(
      <IconButton label="Refresh status" variant="ghost">
        <span>*</span>
      </IconButton>,
    );
    expect(screen.getByRole("button", { name: "Refresh status" })).toBeInTheDocument();
  });

  it("shows FieldError as alert text", () => {
    render(
      <>
        <Input aria-invalid="true" aria-describedby="err" />
        <FieldError id="err" message="Required" />
      </>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
  });

  it("renders RiskBlock without any override control", () => {
    render(<RiskBlock reason="Daily loss limit reached" ruleReference="daily_loss_limit" />);
    const block = screen.getByTestId("risk-block");
    expect(block).toHaveTextContent("Blocked");
    expect(block).toHaveTextContent("Daily loss limit reached");
    expect(block).toHaveTextContent("No override is available");
    expect(block.querySelector("button")).toBeNull();
  });

  it("pairs freshness state with icon and text", () => {
    render(<FreshnessPill state="stale" ageLabel="4m" />);
    expect(screen.getByTestId("freshness-pill")).toHaveTextContent("Stale · 4m");
  });

  it("uses tabular-numeral data numbers with signed channel", () => {
    const { container } = render(
      <DataNumber value="+12.5" tone="positive" signed numeric={12.5} />,
    );
    expect(container.querySelector(".font-data")).toHaveTextContent("▲ +12.5");
  });

  it("supports keyboard-focusable tabs", () => {
    let value = "a";
    const { rerender } = render(
      <Tabs
        aria-label="Sections"
        items={[
          { id: "a", label: "One" },
          { id: "b", label: "Two" },
        ]}
        value={value}
        onChange={(id) => {
          value = id;
        }}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Two" }));
    rerender(
      <Tabs
        aria-label="Sections"
        items={[
          { id: "a", label: "One" },
          { id: "b", label: "Two" },
        ]}
        value={value}
        onChange={(id) => {
          value = id;
        }}
      />,
    );
    expect(screen.getByRole("tab", { name: "Two" })).toHaveAttribute("aria-selected", "true");
  });

  it("exposes tooltip content on focus", () => {
    render(
      <Tooltip content="Helpful hint">
        <Button type="button">Target</Button>
      </Tooltip>,
    );
    fireEvent.focus(screen.getByRole("button", { name: "Target" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Helpful hint");
  });

  it("renders empty / error / stale / blocked / unavailable states with non-color cues", () => {
    render(
      <>
        <EmptyState title="Empty" description="Nothing here" />
        <ErrorState message="Failed" />
        <StaleState ageLabel="5m" />
        <BlockedState message="Not allowed" />
        <UnavailableState message="Down" />
      </>,
    );
    expect(screen.getByTestId("empty-state")).toHaveTextContent("Empty");
    expect(screen.getByTestId("error-state")).toHaveTextContent("Failed");
    expect(screen.getByTestId("stale-state")).toHaveTextContent("Stale data · 5m");
    expect(screen.getByTestId("blocked-state")).toHaveTextContent("Blocked");
    expect(screen.getByTestId("unavailable-state")).toHaveTextContent("Down");
  });
});
