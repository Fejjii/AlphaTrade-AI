"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
export function journalReturnKey(userId?: string, organizationId?: string) {
  return `alphatrade.journal.return:${organizationId}:${userId}`;
}
export function JournalReturnLink() {
  const { user, organization } = useAuth();
  const [href, setHref] = useState("/journal");
  useEffect(() => {
    try {
      const stored = JSON.parse(
        sessionStorage.getItem(journalReturnKey(user?.id, organization?.id)) ??
          "null",
      );
      if (stored?.href?.match(/^\/(journal|knowledge)(\?|$)/))
        setHref(stored.href);
    } catch {
      /* direct link */
    }
  }, [user?.id, organization?.id]);
  return (
    <Link
      href={href}
      className="inline-flex min-h-11 items-center text-sm text-accent"
    >
      ← Back to Journal &amp; Knowledge
    </Link>
  );
}
