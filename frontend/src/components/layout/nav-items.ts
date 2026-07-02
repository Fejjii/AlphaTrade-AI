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
  GraduationCap,
  Inbox,
  LayoutDashboard,
  LineChart,
  ListChecks,
  PlayCircle,
  Radio,
  Scale,
  ScanSearch,
  Settings,
  Shield,
  Target,
  Wallet,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export type NavSection = {
  title: string;
  items: readonly NavItem[];
};

export const navSections: readonly NavSection[] = [
  {
    title: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/portfolio", label: "Paper Portfolio", icon: Wallet },
      { href: "/workspace", label: "AI Workspace", icon: Bot },
    ],
  },
  {
    title: "Paper-first workflow",
    items: [
      { href: "/alerts/review", label: "Setup Review", icon: ScanSearch },
      { href: "/paper-validation/drafts", label: "Paper Drafts", icon: FilePenLine },
      {
        href: "/paper-validation/candidates",
        label: "Paper Validation Queue",
        icon: Inbox,
      },
      { href: "/paper-validation/run-plans", label: "Run Plans", icon: CalendarClock },
      { href: "/paper-validation/run-sessions", label: "Run Sessions", icon: PlayCircle },
      { href: "/alerts", label: "Alerts", icon: Bell },
      { href: "/learning-analytics", label: "Learning Analytics", icon: Brain },
      { href: "/validation-priority", label: "Validation Priority", icon: ListChecks },
      { href: "/coaching", label: "Coaching", icon: GraduationCap },
      { href: "/lessons", label: "Lessons", icon: ListChecks },
      { href: "/strategy-quality", label: "Strategy Quality", icon: Gauge },
    ],
  },
  {
    title: "Legacy proposal flow",
    items: [
      { href: "/proposals", label: "Trade Proposals", icon: FileText },
      { href: "/approvals", label: "Approvals", icon: ClipboardCheck },
      { href: "/positions", label: "Positions", icon: Wallet },
    ],
  },
  {
    title: "Strategy & journal",
    items: [
      { href: "/strategy-lab", label: "Strategy Lab", icon: FlaskConical },
      { href: "/journal", label: "Journal", icon: BookOpen },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
  {
    title: "Market & tools",
    items: [
      { href: "/watchlist", label: "Watchlist", icon: Eye },
      { href: "/market", label: "Market Monitor", icon: LineChart },
      { href: "/manual-levels", label: "Manual Levels", icon: Target },
      { href: "/pre-trade", label: "Pre-Trade", icon: Scale },
      { href: "/watcher", label: "Watcher Scanner", icon: Radio },
      { href: "/market-watcher", label: "Market Watcher", icon: Eye },
    ],
  },
  {
    title: "Platform",
    items: [
      { href: "/knowledge", label: "Knowledge Base", icon: ListChecks },
      { href: "/risk", label: "Risk Settings", icon: Shield },
      { href: "/exchange", label: "Exchange", icon: Radio },
      { href: "/usage", label: "Usage", icon: Gauge },
      { href: "/billing", label: "Billing", icon: CreditCard },
      { href: "/invitations", label: "Invitations", icon: ClipboardCheck },
      { href: "/audit", label: "Audit", icon: Activity },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
] as const;

/** Flat list for mobile nav and other consumers that expect a single array. */
export const navItems: readonly NavItem[] = navSections.flatMap((section) => section.items);
