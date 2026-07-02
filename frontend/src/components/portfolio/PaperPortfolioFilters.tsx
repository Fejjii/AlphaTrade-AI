"use client";

import { Input, Label } from "@/components/ui/input";
import type { PortfolioSourceFilter } from "@/lib/api/types";
import { sourceLabel } from "@/components/portfolio/portfolio-display";

const SOURCE_OPTIONS: PortfolioSourceFilter[] = ["all", "proposal_flow", "paper_validation"];

export function PaperPortfolioFilters({
  startDate,
  endDate,
  source,
  onStartDateChange,
  onEndDateChange,
  onSourceChange,
}: {
  startDate: string;
  endDate: string;
  source: PortfolioSourceFilter;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onSourceChange: (value: PortfolioSourceFilter) => void;
}) {
  return (
    <section
      className="flex flex-wrap items-end gap-4 rounded-lg border border-zinc-800 p-4"
      data-testid="paper-portfolio-filters"
    >
      <div className="space-y-1">
        <Label htmlFor="portfolio-start-date" className="text-xs text-zinc-400">
          From
        </Label>
        <Input
          id="portfolio-start-date"
          type="date"
          value={startDate}
          onChange={(event) => onStartDateChange(event.target.value)}
          className="w-40"
          data-testid="portfolio-filter-start-date"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="portfolio-end-date" className="text-xs text-zinc-400">
          To
        </Label>
        <Input
          id="portfolio-end-date"
          type="date"
          value={endDate}
          onChange={(event) => onEndDateChange(event.target.value)}
          className="w-40"
          data-testid="portfolio-filter-end-date"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="portfolio-source" className="text-xs text-zinc-400">
          Source
        </Label>
        <select
          id="portfolio-source"
          value={source}
          onChange={(event) => onSourceChange(event.target.value as PortfolioSourceFilter)}
          className="h-10 w-44 rounded-md border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-200"
          data-testid="portfolio-filter-source"
        >
          {SOURCE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {sourceLabel(option)}
            </option>
          ))}
        </select>
      </div>
      <p className="text-xs text-zinc-500">
        Read-only filters — updates portfolio metrics without placing trades or changing rules.
      </p>
    </section>
  );
}
