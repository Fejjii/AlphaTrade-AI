import { describe, expect, it } from "vitest";

import {
  getDestinationId,
  getSecondaryItems,
  isNavLinkActive,
  isPrimaryDestinationActive,
  listReachableHrefs,
  MOBILE_BOTTOM_DESTINATION_IDS,
  MOBILE_MENU_DESTINATION_IDS,
  PRIMARY_DESTINATIONS,
  resolvePageIdentity,
  resolveSecondaryActiveHref,
  SECONDARY_NAV,
} from "@/components/layout/navigation-config";
import {
  PHASE_B_CAPABILITY_PATHS,
  PHASE_B_REDIRECTS,
} from "@/lib/navigation/phase-b-redirects";

describe("AT-040 Phase B navigation config", () => {
  it("exposes exactly eight primary destinations", () => {
    expect(PRIMARY_DESTINATIONS).toHaveLength(8);
    expect(PRIMARY_DESTINATIONS.map((d) => d.id)).toEqual([
      "dashboard",
      "plan",
      "signals",
      "validate",
      "journal",
      "analyze",
      "portfolio",
      "settings",
    ]);
    const labels = PRIMARY_DESTINATIONS.map((d) => d.label);
    expect(new Set(labels).size).toBe(8);
  });

  it("keeps mobile bottom destinations and menu destinations disjoint and complete", () => {
    expect(MOBILE_BOTTOM_DESTINATION_IDS).toEqual([
      "dashboard",
      "signals",
      "plan",
      "portfolio",
    ]);
    expect(MOBILE_MENU_DESTINATION_IDS).toEqual([
      "validate",
      "journal",
      "analyze",
      "settings",
    ]);
    const combined = [...MOBILE_BOTTOM_DESTINATION_IDS, ...MOBILE_MENU_DESTINATION_IDS];
    expect(new Set(combined).size).toBe(8);
    expect(combined.sort()).toEqual(PRIMARY_DESTINATIONS.map((d) => d.id).sort());
  });

  it("maps key workflows to the correct primary destination", () => {
    expect(getDestinationId("/")).toBe("dashboard");
    expect(getDestinationId("/tradingview-signals")).toBe("signals");
    expect(getDestinationId("/paper-validation")).toBe("validate");
    expect(getDestinationId("/paper-validation/candidates")).toBe("validate");
    expect(getDestinationId("/paper-validation/candidates/cand-1")).toBe("validate");
    expect(getDestinationId("/paper-signal-orchestration")).toBe("signals");
    expect(getDestinationId("/journal")).toBe("journal");
    expect(getDestinationId("/journal/comparison")).toBe("analyze");
    expect(getDestinationId("/backtests/bt-123")).toBe("validate");
    expect(getDestinationId("/portfolio")).toBe("portfolio");
    expect(getDestinationId("/settings")).toBe("settings");
    expect(getDestinationId("/settings/billing")).toBe("settings");
    expect(getDestinationId("/risk")).toBe("portfolio");
    expect(getDestinationId("/workspace")).toBe("plan");
  });

  it("marks nested routes active without false dashboard matches", () => {
    expect(isNavLinkActive("/paper-validation/candidates/abc", "/paper-validation/candidates")).toBe(
      true,
    );
    expect(isNavLinkActive("/journal/import", "/journal")).toBe(false);
    expect(isNavLinkActive("/", "/")).toBe(true);
    expect(isNavLinkActive("/workspace", "/")).toBe(false);
    const dashboard = PRIMARY_DESTINATIONS[0];
    expect(isPrimaryDestinationActive("/", dashboard)).toBe(true);
    expect(isPrimaryDestinationActive("/portfolio", dashboard)).toBe(false);
  });

  it("keeps advanced placements under destination secondary navigation", () => {
    const signals = SECONDARY_NAV.find((g) => g.destinationId === "signals");
    const validate = SECONDARY_NAV.find((g) => g.destinationId === "validate");
    const settings = SECONDARY_NAV.find((g) => g.destinationId === "settings");
    expect(signals?.items.some((i) => i.href === "/paper-signal-orchestration" && i.advanced)).toBe(
      true,
    );
    expect(validate?.items.some((i) => i.href === "/research-validation" && i.advanced)).toBe(true);
    expect(settings?.items.some((i) => i.href === "/settings/audit" && i.advanced)).toBe(true);
    expect(settings?.items.some((i) => i.href === "/settings/exchange" && i.advanced)).toBe(true);
  });

  it("uses one Billing & Usage L2 section and keeps /risk under Portfolio only", () => {
    const settings = getSecondaryItems("settings");
    const portfolio = getSecondaryItems("portfolio");
    expect(settings.some((i) => i.href === "/settings/billing" && i.label === "Billing & Usage")).toBe(
      true,
    );
    expect(settings.some((i) => i.href === "/settings/usage")).toBe(false);
    expect(settings.some((i) => i.href === "/risk")).toBe(false);
    expect(portfolio.some((i) => i.href === "/risk")).toBe(true);
    expect(getDestinationId("/risk")).toBe("portfolio");
  });

  it("resolves route-aware page identity from centralized navigation config", () => {
    expect(resolvePageIdentity("/").title).toBe("Dashboard");
    expect(resolvePageIdentity("/tradingview-signals").title).toBe("Signals");
    expect(resolvePageIdentity("/tradingview-signals").subtitle).toBeNull();
    expect(resolvePageIdentity("/alerts/review")).toMatchObject({
      title: "Signals",
      subtitle: "Setup Review",
    });
    expect(resolvePageIdentity("/analytics").subtitle).toBeNull();
    expect(resolvePageIdentity("/risk")).toMatchObject({
      title: "Portfolio",
      subtitle: "Risk settings",
    });
    expect(resolvePageIdentity("/settings").subtitle).toBeNull();
    expect(resolvePageIdentity("/paper-validation/candidates/example")).toMatchObject({
      title: "Validate",
      subtitle: "Candidates",
    });
    expect(resolvePageIdentity("/unknown-path").title).toBe("AlphaTrade");
  });

  it("uses FP2-119 secondary label defaults", () => {
    const signals = getSecondaryItems("signals");
    const analyze = getSecondaryItems("analyze");
    const portfolio = getSecondaryItems("portfolio");
    const settings = getSecondaryItems("settings");

    expect(signals.find((i) => i.href === "/tradingview-signals")?.label).toBe("Signals inbox");
    expect(analyze.find((i) => i.href === "/analytics")?.label).toBe("Analytics hub");
    expect(portfolio.find((i) => i.href === "/risk")?.label).toBe("Risk settings");
    expect(settings.find((i) => i.href === "/settings")?.label).toBe("Settings");
    expect(settings.find((i) => i.href === "/settings/billing")?.label).toBe("Billing & Usage");
    expect(settings.find((i) => i.href === "/settings/team")?.label).toBe("Team");
  });

  it("keeps Analytics primary label aligned with the Analytics page (FP2-119 residual)", () => {
    const analytics = PRIMARY_DESTINATIONS.find((d) => d.id === "analyze");
    expect(analytics?.label).toBe("Analytics");
    expect(analytics?.ariaLabel).toBe("Analytics");
    expect(resolvePageIdentity("/analytics")).toMatchObject({
      title: "Analytics",
      subtitle: null,
    });
  });

  it("resolves exactly one secondary active href via longest match", () => {
    const signals = getSecondaryItems("signals");
    const validate = getSecondaryItems("validate");
    const journal = getSecondaryItems("journal");
    const settings = getSecondaryItems("settings");

    expect(resolveSecondaryActiveHref("/alerts", signals)).toBe("/alerts");
    expect(resolveSecondaryActiveHref("/alerts/review", signals)).toBe("/alerts/review");
    expect(resolveSecondaryActiveHref("/paper-validation", validate)).toBe("/paper-validation");
    expect(resolveSecondaryActiveHref("/paper-validation/candidates/example", validate)).toBe(
      "/paper-validation/candidates",
    );
    expect(resolveSecondaryActiveHref("/journal/import", journal)).toBe("/journal/import");
    expect(resolveSecondaryActiveHref("/settings/billing", settings)).toBe("/settings/billing");

    const reviewMatches = signals.filter((item) => isNavLinkActive("/alerts/review", item.href));
    expect(reviewMatches.map((m) => m.href).sort()).toEqual(["/alerts", "/alerts/review"].sort());
    expect(resolveSecondaryActiveHref("/alerts/review", signals)).toBe("/alerts/review");
  });

  it("keeps required capabilities reachable from primary or secondary navigation", () => {
    const reachable = new Set(listReachableHrefs());
    for (const path of PHASE_B_CAPABILITY_PATHS) {
      if (path.startsWith("/backtests/")) {
        expect(getDestinationId(path)).toBe("validate");
        continue;
      }
      expect(reachable.has(path) || getDestinationId(path) !== null).toBe(true);
    }
    expect(reachable.has("/tradingview-signals")).toBe(true);
    expect(reachable.has("/paper-validation")).toBe(true);
    expect(reachable.has("/paper-validation/candidates")).toBe(true);
    expect(reachable.has("/paper-validation/drafts")).toBe(true);
    expect(reachable.has("/paper-validation/run-plans")).toBe(true);
    expect(reachable.has("/paper-validation/run-sessions")).toBe(true);
    expect(reachable.has("/paper-signal-orchestration")).toBe(true);
    expect(reachable.has("/journal")).toBe(true);
    expect(reachable.has("/journal/comparison")).toBe(true);
    expect(reachable.has("/portfolio")).toBe(true);
    expect(reachable.has("/settings")).toBe(true);
    expect(reachable.has("/settings/billing")).toBe(true);
    expect(reachable.has("/risk")).toBe(true);
  });
});

describe("AT-040 Phase B redirects", () => {
  it("defines Settings hub redirects without loops", () => {
    expect(PHASE_B_REDIRECTS.length).toBeGreaterThan(0);
    const sources = new Set(PHASE_B_REDIRECTS.map((r) => r.source));
    const destinations = new Set(PHASE_B_REDIRECTS.map((r) => r.destination));
    for (const rule of PHASE_B_REDIRECTS) {
      expect(rule.source).not.toBe(rule.destination);
      expect(rule.destination.startsWith("/settings/")).toBe(true);
      expect(destinations.has(rule.source)).toBe(false);
    }
    expect(sources.has("/billing")).toBe(true);
    expect(sources.has("/usage")).toBe(true);
    expect(sources.has("/settings/usage")).toBe(true);
    expect(sources.has("/invitations")).toBe(true);
    expect(sources.has("/audit")).toBe(true);
    expect(sources.has("/exchange")).toBe(true);
    expect(
      PHASE_B_REDIRECTS.find((r) => r.source === "/billing")?.destination,
    ).toBe("/settings/billing");
    expect(PHASE_B_REDIRECTS.find((r) => r.source === "/usage")?.destination).toBe(
      "/settings/billing",
    );
  });

  it("does not redirect dynamic capability IDs or paper-validation paths", () => {
    for (const rule of PHASE_B_REDIRECTS) {
      expect(rule.source.includes("[")).toBe(false);
      expect(rule.source.startsWith("/paper-validation")).toBe(false);
      expect(rule.source.startsWith("/backtests")).toBe(false);
      expect(rule.source.startsWith("/strategy-lab")).toBe(false);
    }
  });

  it("preserves query parameters by using path-only redirect sources", () => {
    for (const rule of PHASE_B_REDIRECTS) {
      expect(rule.source.includes("?")).toBe(false);
      expect(rule.destination.includes("?")).toBe(false);
    }
  });
});
