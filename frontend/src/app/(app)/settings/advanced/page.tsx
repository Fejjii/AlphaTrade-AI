import Link from "next/link";

import { ADVANCED_ROUTE_GROUPS, ADVANCED_ROUTES } from "@/components/layout/advanced-routes";
import { PageHeader } from "@/components/ui/page-header";

export default function AdvancedSettingsPage() {
  return (
    <div className="space-y-6" data-testid="settings-advanced-page">
      <PageHeader
        title="Advanced"
        description="Operational, audit, validation, billing, and engineering pages. Trading safety is unchanged."
      />
      {ADVANCED_ROUTE_GROUPS.map((group) => {
        const routes = ADVANCED_ROUTES.filter((route) => route.group === group);
        if (routes.length === 0) return null;
        return (
          <section key={group} className="space-y-2">
            <h2 className="text-sm font-medium text-text-primary">{group}</h2>
            <ul className="grid gap-2 sm:grid-cols-2">
              {routes.map((route) => (
                <li key={route.href}>
                  <Link
                    href={route.href}
                    className="block rounded-card border border-border-subtle bg-surface-1 px-3 py-3 text-sm text-text-primary hover:bg-surface-2"
                  >
                    {route.label}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
