"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

import { navItems } from "./nav-items";

const primaryMobileHrefs = new Set(["/", "/workspace", "/market", "/proposals", "/journal"]);

export function BottomNav() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const mobileItems = navItems.filter((item) => primaryMobileHrefs.has(item.href));
  const moreItems = navItems.filter((item) => !primaryMobileHrefs.has(item.href));
  const moreActive = moreItems.some((item) => item.href === pathname);

  return (
    <>
      <nav
        aria-label="Primary mobile navigation"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-zinc-800 bg-zinc-950/95 backdrop-blur lg:hidden"
      >
        <div className="grid grid-cols-6">
          {mobileItems.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex min-w-0 flex-col items-center gap-1 px-1 py-3 text-[10px]",
                  active ? "text-emerald-300" : "text-zinc-500",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{label.split(" ")[0]}</span>
              </Link>
            );
          })}
          <button
            type="button"
            aria-expanded={moreOpen}
            aria-label="More navigation"
            onClick={() => setMoreOpen((open) => !open)}
            className={cn(
              "flex min-w-0 flex-col items-center gap-1 px-1 py-3 text-[10px]",
              moreActive || moreOpen ? "text-emerald-300" : "text-zinc-500",
            )}
          >
            {moreOpen ? <X className="h-4 w-4 shrink-0" /> : <Menu className="h-4 w-4 shrink-0" />}
            <span>More</span>
          </button>
        </div>
      </nav>

      {moreOpen ? (
        <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={() => setMoreOpen(false)}>
          <div
            className="absolute inset-x-0 bottom-16 max-h-[60vh] overflow-y-auto rounded-t-2xl border border-zinc-800 bg-zinc-950 p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <p className="mb-3 text-xs uppercase tracking-wider text-zinc-500">More pages</p>
            <div className="grid grid-cols-2 gap-2">
              {moreItems.map(({ href, label, icon: Icon }) => {
                const active = pathname === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setMoreOpen(false)}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm",
                      active
                        ? "bg-emerald-500/10 text-emerald-300"
                        : "text-zinc-300 hover:bg-zinc-900",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
