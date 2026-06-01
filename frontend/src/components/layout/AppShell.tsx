"use client";

import { BottomNav, Sidebar } from "@/components/layout/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { PaperModeBanner } from "@/components/PaperModeBanner";
import { AppProvider } from "@/contexts/AppContext";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <div className="min-h-screen overflow-x-hidden bg-zinc-950 text-zinc-100">
        <div className="flex min-h-screen min-w-0">
          <Sidebar />
          <div className="flex min-h-screen min-w-0 flex-1 flex-col pb-20 lg:pb-0">
            <TopBar />
            <main className="mx-auto w-full min-w-0 max-w-7xl flex-1 space-y-6 overflow-x-hidden px-4 py-6 lg:px-6">
              <PaperModeBanner />
              {children}
            </main>
          </div>
        </div>
        <BottomNav />
      </div>
    </AppProvider>
  );
}
