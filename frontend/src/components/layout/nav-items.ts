/**
 * Compatibility shim — Phase B uses `navigation-config.ts` as the source of truth.
 * Kept so any residual imports continue to resolve during the transition.
 */
import {
  listReachableHrefs,
  PRIMARY_DESTINATIONS,
  SECONDARY_NAV,
  type NavLink,
} from "@/components/layout/navigation-config";

export type NavItem = NavLink;

export type NavSection = {
  title: string;
  items: readonly NavItem[];
};

export const navSections: readonly NavSection[] = [
  {
    title: "Primary",
    items: PRIMARY_DESTINATIONS.map(({ href, label, icon }) => ({ href, label, icon })),
  },
  ...SECONDARY_NAV.map((group) => ({
    title: group.destinationId,
    items: group.items,
  })),
];

export const navItems: readonly NavItem[] = [
  ...PRIMARY_DESTINATIONS.map(({ href, label, icon }) => ({ href, label, icon })),
  ...SECONDARY_NAV.flatMap((group) => [...group.items]),
];

export { listReachableHrefs };
