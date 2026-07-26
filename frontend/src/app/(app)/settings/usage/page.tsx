"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Compatibility shim — Billing & Usage canonical route is /settings/billing.
 * next.config also redirects /settings/usage → /settings/billing.
 */
export default function SettingsUsageRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/settings/billing#usage");
  }, [router]);
  return null;
}
