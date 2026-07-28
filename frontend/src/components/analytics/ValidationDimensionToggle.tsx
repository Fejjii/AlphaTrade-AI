"use client";

import { useCallback, useRef, type KeyboardEvent } from "react";

import {
  VALIDATION_DIMENSION_OPTIONS,
  type ValidationDimension,
} from "./filterValidation";
import { VALIDATION_DIMENSION_LABELS } from "./validationDimensionCopy";

export type ValidationDimensionToggleProps = {
  value: ValidationDimension;
  onChange: (dimension: ValidationDimension) => void;
  "data-testid"?: string;
};

export function ValidationDimensionToggle({
  value,
  onChange,
  "data-testid": testId = "validation-dimension-toggle",
}: ValidationDimensionToggleProps) {
  const buttonRefs = useRef<Partial<Record<ValidationDimension, HTMLButtonElement | null>>>({});

  const focusOption = useCallback((dimension: ValidationDimension) => {
    buttonRefs.current[dimension]?.focus();
  }, []);

  const selectAndFocus = useCallback(
    (dimension: ValidationDimension) => {
      onChange(dimension);
      focusOption(dimension);
    },
    [focusOption, onChange],
  );

  const moveSelection = useCallback(
    (offset: number) => {
      const currentIndex = VALIDATION_DIMENSION_OPTIONS.indexOf(value);
      const nextIndex =
        (currentIndex + offset + VALIDATION_DIMENSION_OPTIONS.length) %
        VALIDATION_DIMENSION_OPTIONS.length;
      selectAndFocus(VALIDATION_DIMENSION_OPTIONS[nextIndex]!);
    },
    [selectAndFocus, value],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, option: ValidationDimension) => {
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
          selectAndFocus(VALIDATION_DIMENSION_OPTIONS[0]!);
          break;
        case "End":
          event.preventDefault();
          selectAndFocus(
            VALIDATION_DIMENSION_OPTIONS[VALIDATION_DIMENSION_OPTIONS.length - 1]!,
          );
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
      aria-label="Validation setup-performance dimension"
      className="flex flex-wrap gap-2"
      data-testid={testId}
    >
      {VALIDATION_DIMENSION_OPTIONS.map((option) => {
        const selected = option === value;
        return (
          <button
            key={option}
            ref={(element) => {
              buttonRefs.current[option] = element;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            data-testid={`validation-dimension-${option}`}
            className={
              selected
                ? "rounded-control border border-accent bg-accent/15 px-3 py-1.5 text-sm text-text-primary"
                : "rounded-control border border-border-subtle bg-surface-0 px-3 py-1.5 text-sm text-text-secondary hover:border-border-strong"
            }
            onClick={() => selectAndFocus(option)}
            onKeyDown={(event) => handleKeyDown(event, option)}
          >
            {VALIDATION_DIMENSION_LABELS[option]}
          </button>
        );
      })}
    </div>
  );
}
