"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useId, useState } from "react";

import { MobileMenuSheet } from "@/components/layout/MobileMenuSheet";
import {
  getDestinationId,
  getPrimaryDestination,
  isPrimaryDestinationActive,
  MOBILE_BOTTOM_DESTINATION_IDS,
  MOBILE_MENU_DESTINATION_IDS,
} from "@/components/layout/navigation-config";
import { cn } from "@/lib/utils";

export function MobileBottomNavigation() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuPanelId = useId();
  const currentDestination = getDestinationId(pathname);
  const menuActive =
    menuOpen ||
    (currentDestination !== null && MOBILE_MENU_DESTINATION_IDS.includes(currentDestination));

  return (
    <>
      <nav
        aria-label="Primary mobile"
        data-testid="mobile-bottom-navigation"
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 border-t border-border-subtle bg-surface-0/95 backdrop-blur",
          "pb-[env(safe-area-inset-bottom,0px)] lg:hidden",
        )}
      >
        <div className="grid grid-cols-5">
          {MOBILE_BOTTOM_DESTINATION_IDS.map((id) => {
            const destination = getPrimaryDestination(id);
            const { href, label, icon: Icon, ariaLabel } = destination;
            const active = !menuOpen && isPrimaryDestinationActive(pathname, destination);
            return (
              <Link
                key={id}
                href={href}
                aria-label={ariaLabel}
                aria-current={active ? "page" : undefined}
                data-destination={id}
                onClick={() => setMenuOpen(false)}
                className={cn(
                  "flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 px-1 text-caption",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                  active ? "text-accent" : "text-text-muted",
                )}
              >
                <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                <span className="truncate">{label}</span>
              </Link>
            );
          })}
          <button
            type="button"
            aria-expanded={menuOpen}
            aria-controls={menuPanelId}
            aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
            data-testid="mobile-menu-button"
            onClick={() => setMenuOpen((open) => !open)}
            className={cn(
              "flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 px-1 text-caption",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
              menuActive ? "text-accent" : "text-text-muted",
            )}
          >
            {menuOpen ? (
              <X className="h-5 w-5 shrink-0" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5 shrink-0" aria-hidden="true" />
            )}
            <span>Menu</span>
          </button>
        </div>
      </nav>

      <div id={menuPanelId}>
        <MobileMenuSheet open={menuOpen} onClose={() => setMenuOpen(false)} />
      </div>
    </>
  );
}
