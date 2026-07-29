"use client";

import { useCallback, useRef, type KeyboardEvent } from "react";

import type { SetupGroupBy } from "./filterValidation";
import { setupGroupCopy } from "./setupGroupCopy";

const OPTIONS: { value: SetupGroupBy; label: string }[] = [
  { value: "setup", label: "Setup" },
  { value: "setup_version", label: "Setup version" },
  { value: "strategy", label: "Strategy" },
];

const OPTION_VALUES = OPTIONS.map((option) => option.value);

export type SetupGroupToggleProps = {
  value: SetupGroupBy;
  onChange: (value: SetupGroupBy) => void;
};

/**
 * Radio group with the roving-tabindex pattern: one tab stop for the group,
 * arrow keys and Home/End move between options (FP2-217).
 */
export function SetupGroupToggle({ value, onChange }: SetupGroupToggleProps) {
  const ariaLabel = setupGroupCopy(value).groupToggleAriaLabel;
  const buttonRefs = useRef<Partial<Record<SetupGroupBy, HTMLButtonElement | null>>>({});

  const selectAndFocus = useCallback(
    (option: SetupGroupBy) => {
      onChange(option);
      buttonRefs.current[option]?.focus();
    },
    [onChange],
  );

  const moveSelection = useCallback(
    (offset: number) => {
      const currentIndex = OPTION_VALUES.indexOf(value);
      const nextIndex = (currentIndex + offset + OPTION_VALUES.length) % OPTION_VALUES.length;
      selectAndFocus(OPTION_VALUES[nextIndex]!);
    },
    [selectAndFocus, value],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, option: SetupGroupBy) => {
      switch (event.key) {
        case "ArrowLeft":
        case "ArrowUp":
          event.preventDefault();
          moveSelection(-1);
          break;
        case "ArrowRight":
        case "ArrowDown":
          event.preventDefault();
          moveSelection(1);
          break;
        case "Home":
          event.preventDefault();
          selectAndFocus(OPTION_VALUES[0]!);
          break;
        case "End":
          event.preventDefault();
          selectAndFocus(OPTION_VALUES[OPTION_VALUES.length - 1]!);
          break;
        case " ":
        case "Enter":
          event.preventDefault();
          if (option !== value) selectAndFocus(option);
          break;
        default:
          break;
      }
    },
    [moveSelection, selectAndFocus, value],
  );

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="flex flex-wrap gap-2"
      data-testid="setup-group-toggle"
    >
      {OPTIONS.map((option) => {
        const selected = value === option.value;
        return (
          <button
            key={option.value}
            ref={(element) => {
              buttonRefs.current[option.value] = element;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            data-testid={`setup-group-${option.value}`}
            className={
              selected
                ? "inline-flex min-h-11 items-center rounded-control border border-accent bg-accent/15 px-3 py-1.5 text-sm text-text-primary"
                : "inline-flex min-h-11 items-center rounded-control border border-border-subtle bg-surface-0 px-3 py-1.5 text-sm text-text-secondary hover:border-border-strong"
            }
            onClick={() => selectAndFocus(option.value)}
            onKeyDown={(event) => handleKeyDown(event, option.value)}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
