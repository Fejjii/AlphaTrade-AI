"use client";

import { NotFinancialAdviceBanner } from "@/components/layout/NotFinancialAdviceBanner";
import { BottomNav, Sidebar } from "@/components/layout/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { PaperModeBanner } from "@/components/PaperModeBanner";
import { AppProvider } from "@/contexts/AppContext";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <div className="min-h-screen overflow-x-hidden bg-background text-text-primary">
        <div className="flex min-h-screen min-w-0">
          <Sidebar />
          <div className="flex min-h-screen min-w-0 flex-1 flex-col pb-20 lg:pb-0">
            <TopBar />
            <main className="mx-auto w-full min-w-0 max-w-content flex-1 space-y-section overflow-x-hidden px-gutter py-6 lg:px-gutter-lg">
              <PaperModeBanner />
              <NotFinancialAdviceBanner />
              {children}
            </main>
          </div>
        </div>
        <BottomNav />
      </div>
    </AppProvider>
  );
}
