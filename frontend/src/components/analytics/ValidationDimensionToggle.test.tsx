import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ValidationDimensionToggle } from "./ValidationDimensionToggle";

describe("ValidationDimensionToggle", () => {
  afterEach(() => cleanup());

  it("uses roving tabIndex with the selected option tabbable", () => {
    render(<ValidationDimensionToggle value="condition" onChange={vi.fn()} />);
    expect(screen.getByTestId("validation-dimension-condition")).toHaveAttribute("tabIndex", "0");
    expect(screen.getByTestId("validation-dimension-timeframe")).toHaveAttribute("tabIndex", "-1");
  });

  it("moves selection and focus with arrow keys", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <ValidationDimensionToggle value="condition" onChange={onChange} />,
    );
    const condition = screen.getByTestId("validation-dimension-condition");
    condition.focus();
    fireEvent.keyDown(condition, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("timeframe");
    rerender(<ValidationDimensionToggle value="timeframe" onChange={onChange} />);
    expect(screen.getByTestId("validation-dimension-timeframe")).toHaveFocus();
    expect(screen.getByTestId("validation-dimension-timeframe")).toHaveAttribute("tabIndex", "0");
  });

  it("supports Home and End", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <ValidationDimensionToggle value="symbol" onChange={onChange} />,
    );
    const symbol = screen.getByTestId("validation-dimension-symbol");
    symbol.focus();
    fireEvent.keyDown(symbol, { key: "Home" });
    expect(onChange).toHaveBeenCalledWith("condition");
    rerender(<ValidationDimensionToggle value="condition" onChange={onChange} />);
    onChange.mockClear();
    fireEvent.keyDown(screen.getByTestId("validation-dimension-condition"), { key: "End" });
    expect(onChange).toHaveBeenCalledWith("confidence_bucket");
  });

  it("activates with Space and Enter without re-selecting the current value", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <ValidationDimensionToggle value="condition" onChange={onChange} />,
    );
    const direction = screen.getByTestId("validation-dimension-direction");
    direction.focus();
    fireEvent.keyDown(direction, { key: " " });
    expect(onChange).toHaveBeenCalledWith("direction");
    onChange.mockClear();
    rerender(<ValidationDimensionToggle value="direction" onChange={onChange} />);
    fireEvent.keyDown(screen.getByTestId("validation-dimension-direction"), { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();
  });
});
