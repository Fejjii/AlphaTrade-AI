"use client";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingState } from "@/components/states";
import { AuthProvider, useRequireAuth } from "@/contexts/AuthContext";

function ProtectedShell({ children }: { children: React.ReactNode }) {
  const auth = useRequireAuth();
  if (auth.loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <LoadingState label="Checking session…" />
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ProtectedShell>{children}</ProtectedShell>
    </AuthProvider>
  );
}
