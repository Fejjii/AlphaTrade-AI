"use client";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingState } from "@/components/states";
import { AppProvider } from "@/contexts/AppContext";
import { AuthProvider, useRequireAuth } from "@/contexts/AuthContext";

function ProtectedShell({ children }: { children: React.ReactNode }) {
  const auth = useRequireAuth();
  if (auth.loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <LoadingState label="Checking session…" />
      </div>
    );
  }
  // Fail closed: never render protected content while the redirect to /login runs.
  if (!auth.isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <LoadingState label="Redirecting to sign in…" />
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // AppProvider owns the single shared /health, providers, and kill-switch
  // source; AuthProvider consumes it instead of fetching /health itself.
  return (
    <AppProvider>
      <AuthProvider>
        <ProtectedShell>{children}</ProtectedShell>
      </AuthProvider>
    </AppProvider>
  );
}
