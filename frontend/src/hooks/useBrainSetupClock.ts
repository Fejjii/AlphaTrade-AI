"use client";

import { useEffect, useState } from "react";
import type { BrainSetup } from "@/lib/api/brain-types";

/** Expire stored evidence locally, even while a refresh is unresolved. */
export function useBrainSetupClock(setups: readonly BrainSetup[]) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { setNow(Date.now()); }, [setups]);
  useEffect(() => {
    const current = Date.now();
    const deadlines = setups.flatMap(setup => [setup.fresh_until, setup.expires_at])
      .map(value => Date.parse(value)).filter(value => Number.isFinite(value) && value > current);
    if (!deadlines.length) return;
    const timer = setTimeout(() => setNow(Date.now()), Math.min(2_147_483_647, Math.min(...deadlines) - current));
    return () => clearTimeout(timer);
  }, [setups, now]);
  return now;
}

export function displayedBrainSetup(setup: BrainSetup, now: number): BrainSetup {
  return {
    ...setup,
    freshness: now >= Date.parse(setup.fresh_until) ? "STALE" : setup.freshness,
    state: now >= Date.parse(setup.expires_at) && !["COMPLETED", "INVALIDATED"].includes(setup.state)
      ? "EXPIRED" : setup.state,
  };
}
