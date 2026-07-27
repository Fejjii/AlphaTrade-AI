"use client";

import type { SetupGroupBy } from "./filterValidation";
import { setupGroupCopy } from "./setupGroupCopy";

const OPTIONS: { value: SetupGroupBy; label: string }[] = [
  { value: "setup", label: "Setup" },
  { value: "setup_version", label: "Setup version" },
  { value: "strategy", label: "Strategy" },
];

export type SetupGroupToggleProps = {
  value: SetupGroupBy;
  onChange: (value: SetupGroupBy) => void;
};

export function SetupGroupToggle({ value, onChange }: SetupGroupToggleProps) {
  const ariaLabel = setupGroupCopy(value).groupToggleAriaLabel;

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
            type="button"
            role="radio"
            aria-checked={selected}
            data-testid={`setup-group-${option.value}`}
            className={
              selected
                ? "rounded-control border border-accent bg-accent/15 px-3 py-1.5 text-sm text-text-primary"
                : "rounded-control border border-border-subtle bg-surface-0 px-3 py-1.5 text-sm text-text-secondary hover:border-border-strong"
            }
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onChange(option.value);
              }
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
