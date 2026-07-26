import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Brain,
  CalendarClock,
  ClipboardCheck,
  CreditCard,
  Eye,
  FilePenLine,
  FileText,
  FlaskConical,
  Gauge,
  GitCompare,
  GraduationCap,
  Inbox,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Menu,
  Microscope,
  PlayCircle,
  Radio,
  Scale,
  ScanSearch,
  Settings,
  Shield,
  Target,
  Upload,
  Wallet,
} from "lucide-react";

export type DestinationId =
  | "dashboard"
  | "plan"
  | "signals"
  | "validate"
  | "journal"
  | "analyze"
  | "portfolio"
  | "settings";

export type NavLink = {
  href: string;
  label: string;
  icon: LucideIcon;
  advanced?: boolean;
};

export type PrimaryDestination = {
  id: DestinationId;
  label: string;
  href: string;
  icon: LucideIcon;
  /** Accessible name for landmark links */
  ariaLabel: string;
};

export type SecondaryNavGroup = {
  destinationId: DestinationId;
  items: readonly NavLink[];
};

/** Exactly eight primary destinations (AT-039 §2.1 / §3.1). */
export const PRIMARY_DESTINATIONS: readonly PrimaryDestination[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
    ariaLabel: "Dashboard",
  },
  {
    id: "plan",
    label: "Plan",
    href: "/workspace",
    icon: Bot,
    ariaLabel: "Plan",
  },
  {
    id: "signals",
    label: "Signals",
    href: "/tradingview-signals",
    icon: Radio,
    ariaLabel: "Signals",
  },
  {
    id: "validate",
    label: "Validate",
    href: "/paper-validation/candidates",
    icon: Inbox,
    ariaLabel: "Validate",
  },
  {
    id: "journal",
    label: "Journal",
    href: "/journal",
    icon: BookOpen,
    ariaLabel: "Journal",
  },
  {
    id: "analyze",
    label: "Analyze",
    href: "/analytics",
    icon: BarChart3,
    ariaLabel: "Analyze",
  },
  {
    id: "portfolio",
    label: "Portfolio",
    href: "/portfolio",
    icon: Wallet,
    ariaLabel: "Portfolio",
  },
  {
    id: "settings",
    label: "Settings",
    href: "/settings",
    icon: Settings,
    ariaLabel: "Settings",
  },
] as const;

/** Mobile bottom bar: Dashboard, Signals, Plan (center), Portfolio, Menu. */
export const MOBILE_BOTTOM_DESTINATION_IDS: readonly DestinationId[] = [
  "dashboard",
  "signals",
  "plan",
  "portfolio",
] as const;

/** Menu sheet destinations (remaining four). */
export const MOBILE_MENU_DESTINATION_IDS: readonly DestinationId[] = [
  "validate",
  "journal",
  "analyze",
  "settings",
] as const;

export const MENU_NAV_ITEM = {
  id: "menu" as const,
  label: "Menu",
  icon: Menu,
  ariaLabel: "Open navigation menu",
};

export const SECONDARY_NAV: readonly SecondaryNavGroup[] = [
  {
    destinationId: "plan",
    items: [
      { href: "/workspace", label: "Workspace", icon: Bot },
      { href: "/proposals", label: "Proposals", icon: FileText },
      { href: "/approvals", label: "Approvals", icon: ClipboardCheck },
      { href: "/pre-trade", label: "Pre-Trade", icon: Scale },
      { href: "/manual-levels", label: "Manual Levels", icon: Target },
      { href: "/strategy-lab", label: "Strategy Lab", icon: FlaskConical },
    ],
  },
  {
    destinationId: "signals",
    items: [
      { href: "/tradingview-signals", label: "TradingView Signals", icon: Radio },
      { href: "/alerts", label: "Alerts", icon: Bell },
      { href: "/alerts/review", label: "Setup Review", icon: ScanSearch },
      { href: "/watcher", label: "Watcher Scanner", icon: Radio },
      { href: "/market-watcher", label: "Market Watcher", icon: Eye },
      { href: "/market", label: "Market Monitor", icon: LineChart },
      { href: "/watchlist", label: "Watchlist", icon: Eye },
      {
        href: "/paper-signal-orchestration",
        label: "Signal Orchestration",
        icon: GitCompare,
        advanced: true,
      },
    ],
  },
  {
    destinationId: "validate",
    items: [
      { href: "/paper-validation/drafts", label: "Drafts", icon: FilePenLine },
      { href: "/paper-validation/candidates", label: "Candidates", icon: Inbox },
      { href: "/paper-validation/run-plans", label: "Run Plans", icon: CalendarClock },
      { href: "/paper-validation/run-sessions", label: "Run Sessions", icon: PlayCircle },
      { href: "/validation-priority", label: "Validation Priority", icon: ListChecks },
      {
        href: "/research-validation",
        label: "Research Validation",
        icon: Microscope,
        advanced: true,
      },
    ],
  },
  {
    destinationId: "journal",
    items: [
      { href: "/journal", label: "Journal", icon: BookOpen },
      { href: "/journal/import", label: "Import", icon: Upload },
      { href: "/lessons", label: "Lessons", icon: GraduationCap },
      { href: "/knowledge", label: "Knowledge", icon: ListChecks },
    ],
  },
  {
    destinationId: "analyze",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/journal/statistics", label: "Journal Statistics", icon: BarChart3 },
      { href: "/journal/comparison", label: "Human vs System", icon: GitCompare },
      { href: "/learning-analytics", label: "Learning Analytics", icon: Brain },
      { href: "/coaching", label: "Coaching", icon: GraduationCap },
      { href: "/strategy-quality", label: "Strategy Quality", icon: Gauge },
    ],
  },
  {
    destinationId: "portfolio",
    items: [
      { href: "/portfolio", label: "Overview", icon: Wallet },
      { href: "/positions", label: "Positions", icon: Wallet },
      { href: "/risk", label: "Risk & Cooldowns", icon: Shield },
    ],
  },
  {
    destinationId: "settings",
    items: [
      { href: "/settings", label: "Profile", icon: Settings },
      // Billing & Usage are one L2 section; /risk config split is deferred to Phase C.
      { href: "/settings/billing", label: "Billing & Usage", icon: CreditCard },
      { href: "/settings/team", label: "Team", icon: ClipboardCheck },
      { href: "/settings/audit", label: "Audit", icon: Activity, advanced: true },
      { href: "/settings/exchange", label: "Exchange diagnostics", icon: Radio, advanced: true },
    ],
  },
] as const;

/** Ordered prefix rules; first match wins. Dashboard `/` is exact-only. */
const DESTINATION_MATCHERS: readonly { id: DestinationId; match: (pathname: string) => boolean }[] =
  [
    {
      id: "validate",
      match: (p) =>
        p.startsWith("/paper-validation") ||
        p.startsWith("/validation-priority") ||
        p.startsWith("/research-validation") ||
        p.startsWith("/backtests"),
    },
    {
      id: "signals",
      match: (p) =>
        p.startsWith("/tradingview-signals") ||
        p.startsWith("/alerts") ||
        p.startsWith("/watcher") ||
        p.startsWith("/market-watcher") ||
        p.startsWith("/market") ||
        p.startsWith("/watchlist") ||
        p.startsWith("/paper-signal-orchestration"),
    },
    {
      id: "analyze",
      match: (p) =>
        p.startsWith("/analytics") ||
        p.startsWith("/journal/statistics") ||
        p.startsWith("/journal/comparison") ||
        p.startsWith("/learning-analytics") ||
        p.startsWith("/coaching") ||
        p.startsWith("/strategy-quality"),
    },
    {
      id: "journal",
      match: (p) =>
        p === "/journal" ||
        p.startsWith("/journal/") ||
        p.startsWith("/lessons") ||
        p.startsWith("/knowledge"),
    },
    {
      id: "plan",
      match: (p) =>
        p.startsWith("/workspace") ||
        p.startsWith("/proposals") ||
        p.startsWith("/approvals") ||
        p.startsWith("/pre-trade") ||
        p.startsWith("/manual-levels") ||
        p.startsWith("/strategy-lab"),
    },
    {
      id: "portfolio",
      match: (p) => p.startsWith("/portfolio") || p.startsWith("/positions") || p === "/risk",
    },
    {
      id: "settings",
      match: (p) =>
        p.startsWith("/settings") ||
        p.startsWith("/billing") ||
        p.startsWith("/usage") ||
        p.startsWith("/invitations") ||
        p.startsWith("/audit") ||
        p.startsWith("/exchange"),
    },
    { id: "dashboard", match: (p) => p === "/" },
  ];

export function getDestinationId(pathname: string): DestinationId | null {
  for (const rule of DESTINATION_MATCHERS) {
    if (rule.match(pathname)) return rule.id;
  }
  return null;
}

export function getPrimaryDestination(id: DestinationId): PrimaryDestination {
  const found = PRIMARY_DESTINATIONS.find((d) => d.id === id);
  if (!found) {
    throw new Error(`Unknown destination: ${id}`);
  }
  return found;
}

export function getSecondaryItems(destinationId: DestinationId): readonly NavLink[] {
  return SECONDARY_NAV.find((group) => group.destinationId === destinationId)?.items ?? [];
}

export function isNavLinkActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/settings") return pathname === "/settings";
  if (href === "/journal") return pathname === "/journal";
  if (href === "/risk") return pathname === "/risk" || pathname.startsWith("/risk/");
  if (href === "/alerts") return pathname === "/alerts" || pathname.startsWith("/alerts/");
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Exactly one secondary link may be current: prefer the longest matching href.
 * Dynamic detail routes without a more-specific item keep the parent match.
 */
export function resolveSecondaryActiveHref(
  pathname: string,
  items: readonly NavLink[],
): string | null {
  const matches = items
    .filter((item) => isNavLinkActive(pathname, item.href))
    .sort((a, b) => b.href.length - a.href.length);
  return matches[0]?.href ?? null;
}

export function isPrimaryDestinationActive(pathname: string, destination: PrimaryDestination): boolean {
  return getDestinationId(pathname) === destination.id;
}

/** Flat reachability map used by tests — every retained capability path. */
export function listReachableHrefs(): string[] {
  const hrefs = new Set<string>();
  for (const dest of PRIMARY_DESTINATIONS) {
    hrefs.add(dest.href);
  }
  for (const group of SECONDARY_NAV) {
    for (const item of group.items) {
      hrefs.add(item.href);
    }
  }
  return [...hrefs].sort();
}
