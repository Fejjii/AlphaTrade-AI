import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState, type ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  BlockedState,
  EmptyState,
  ErrorState,
  LimitationsState,
  StaleState,
  UnavailableState,
} from "@/components/states";
import { Button } from "@/components/ui/button";
import { DataNumber } from "@/components/ui/data-number";
import { FieldError, Input } from "@/components/ui/input";
import { FreshnessPill } from "@/components/ui/freshness-pill";
import { IconButton } from "@/components/ui/icon-button";
import { PageHeader } from "@/components/ui/page-header";
import {
  isPaperModeConfirmed,
  PaperModeIndicator,
} from "@/components/ui/paper-mode-indicator";
import { RiskBlock } from "@/components/ui/risk-block";
import { TabPanel, Tabs } from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";

afterEach(() => cleanup());

function ControlledTabs({
  idPrefix = "demo",
  withDisabled = false,
}: {
  idPrefix?: string;
  withDisabled?: boolean;
}): ReactElement {
  const items = withDisabled
    ? [
        { id: "a", label: "One" },
        { id: "b", label: "Two", disabled: true },
        { id: "c", label: "Three" },
      ]
    : [
        { id: "a", label: "One" },
        { id: "b", label: "Two" },
        { id: "c", label: "Three" },
      ];
  const [value, setValue] = useState("a");
  return (
    <>
      <Tabs
        aria-label="Sections"
        idPrefix={idPrefix}
        items={items}
        value={value}
        onChange={setValue}
      />
      <TabPanel id="a" activeId={value} idPrefix={idPrefix}>
        Panel A
      </TabPanel>
      <TabPanel id="b" activeId={value} idPrefix={idPrefix}>
        Panel B
      </TabPanel>
      <TabPanel id="c" activeId={value} idPrefix={idPrefix}>
        Panel C
      </TabPanel>
    </>
  );
}

describe("AT-040 design-system primitives", () => {
  it("renders PageHeader with restrained title hierarchy", () => {
    render(
      <PageHeader
        title="Dashboard"
        description="Paper workspace"
        meta={<PaperModeIndicator active />}
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

  it("exposes tooltip content on focus", () => {
    render(
      <Tooltip content="Helpful hint">
        <Button type="button">Target</Button>
      </Tooltip>,
    );
    fireEvent.focus(screen.getByRole("button", { name: "Target" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Helpful hint");
  });

  it("renders empty / error / stale / blocked / unavailable / limitations states", () => {
    render(
      <>
        <EmptyState title="Empty" description="Nothing here" />
        <ErrorState message="Failed" />
        <StaleState ageLabel="5m" />
        <LimitationsState message="Coverage incomplete" items={["Sample too small"]} />
        <BlockedState message="Not allowed" />
        <UnavailableState message="Down" />
      </>,
    );
    expect(screen.getByTestId("empty-state")).toHaveTextContent("Empty");
    expect(screen.getByTestId("error-state")).toHaveTextContent("Failed");
    expect(screen.getByTestId("stale-state")).toHaveTextContent("Stale data · 5m");
    expect(screen.getByTestId("limitations-state")).toHaveTextContent("Limitations");
    expect(screen.getByTestId("limitations-state")).toHaveTextContent("Coverage incomplete");
    expect(screen.getByTestId("limitations-state")).not.toHaveTextContent("Stale data");
    expect(screen.getByTestId("blocked-state")).toHaveTextContent("Blocked");
    expect(screen.getByTestId("unavailable-state")).toHaveTextContent("Down");
  });
});

describe("AT-040 PaperModeIndicator fail-closed", () => {
  it("defaults to unconfirmed paper mode", () => {
    render(<PaperModeIndicator />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("shows confirmed paper mode only when active is true", () => {
    render(<PaperModeIndicator active />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("treats real trading enabled as unconfirmed", () => {
    expect(isPaperModeConfirmed("paper", true)).toBe(false);
    render(<PaperModeIndicator active={isPaperModeConfirmed("paper", true)} />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("treats non-paper execution mode as unconfirmed", () => {
    expect(isPaperModeConfirmed("live", false)).toBe(false);
    render(<PaperModeIndicator active={isPaperModeConfirmed("live", false)} />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("treats missing safety data as unconfirmed", () => {
    expect(isPaperModeConfirmed(null, null)).toBe(false);
    expect(isPaperModeConfirmed(undefined, undefined)).toBe(false);
    render(<PaperModeIndicator active={isPaperModeConfirmed(null, null)} />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("treats partial / loading safety data as unconfirmed", () => {
    expect(isPaperModeConfirmed("paper", null)).toBe(false);
    expect(isPaperModeConfirmed(null, false)).toBe(false);
    render(<PaperModeIndicator active={isPaperModeConfirmed("paper", null)} />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("confirms only paper + real trading disabled", () => {
    expect(isPaperModeConfirmed("paper", false)).toBe(true);
  });
});

describe("AT-040 Tabs keyboard accessibility", () => {
  it("moves focus with ArrowRight and activates with Enter", () => {
    render(<ControlledTabs />);
    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: "One" }).focus();
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Two" })).toHaveFocus();
    fireEvent.keyDown(tablist, { key: "Enter" });
    expect(screen.getByRole("tab", { name: "Two" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel B");
  });

  it("moves focus with ArrowLeft and activates with Space", () => {
    render(<ControlledTabs />);
    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: "One" }).focus();
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Three" })).toHaveFocus();
    fireEvent.keyDown(tablist, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Two" })).toHaveFocus();
    fireEvent.keyDown(tablist, { key: " " });
    expect(screen.getByRole("tab", { name: "Two" })).toHaveAttribute("aria-selected", "true");
  });

  it("supports Home and End keys", () => {
    render(<ControlledTabs />);
    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: "One" }).focus();
    fireEvent.keyDown(tablist, { key: "End" });
    expect(screen.getByRole("tab", { name: "Three" })).toHaveFocus();
    fireEvent.keyDown(tablist, { key: "Home" });
    expect(screen.getByRole("tab", { name: "One" })).toHaveFocus();
  });

  it("wraps focus at ends", () => {
    render(<ControlledTabs />);
    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: "One" }).focus();
    fireEvent.keyDown(tablist, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Three" })).toHaveFocus();
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "One" })).toHaveFocus();
  });

  it("skips disabled tabs during keyboard navigation", () => {
    render(<ControlledTabs withDisabled />);
    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: "One" }).focus();
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Three" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Two" })).toBeDisabled();
  });

  it("keeps click activation working", () => {
    render(<ControlledTabs />);
    fireEvent.click(screen.getByRole("tab", { name: "Three" }));
    expect(screen.getByRole("tab", { name: "Three" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel C");
  });

  it("links tabs and panels with aria-controls / aria-labelledby", () => {
    render(<ControlledTabs idPrefix="link" />);
    const selected = screen.getByRole("tab", { name: "One" });
    expect(selected).toHaveAttribute("id", "link-tab-a");
    expect(selected).toHaveAttribute("aria-controls", "link-tabpanel-a");
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("id", "link-tabpanel-a");
    expect(panel).toHaveAttribute("aria-labelledby", "link-tab-a");
  });

  it("avoids identifier collisions across multiple Tabs instances", () => {
    render(
      <>
        <Tabs
          aria-label="First"
          idPrefix="g1"
          items={[
            { id: "a", label: "A1" },
            { id: "b", label: "B1" },
          ]}
          value="a"
          onChange={vi.fn()}
        />
        <Tabs
          aria-label="Second"
          idPrefix="g2"
          items={[
            { id: "a", label: "A2" },
            { id: "b", label: "B2" },
          ]}
          value="a"
          onChange={vi.fn()}
        />
      </>,
    );
    const first = screen.getByRole("tablist", { name: "First" });
    const second = screen.getByRole("tablist", { name: "Second" });
    expect(within(first).getByRole("tab", { name: "A1" })).toHaveAttribute("id", "g1-tab-a");
    expect(within(second).getByRole("tab", { name: "A2" })).toHaveAttribute("id", "g2-tab-a");
    expect(within(first).getByRole("tab", { name: "A1" }).id).not.toBe(
      within(second).getByRole("tab", { name: "A2" }).id,
    );
  });
});
