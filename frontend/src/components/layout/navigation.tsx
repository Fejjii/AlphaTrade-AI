"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { navItems } from "./nav-items";

export { BottomNav } from "./MobileMoreNav";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 border-r border-zinc-800 bg-zinc-950/80 lg:flex lg:flex-col">
      <div className="border-b border-zinc-800 px-5 py-5">
        <p className="text-xs uppercase tracking-[0.2em] text-emerald-400">AlphaTrade AI</p>
        <h1 className="mt-1 text-lg font-semibold text-zinc-50">Trading Copilot</h1>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                active
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
