import { BottomNav } from "@/components/layout/bottom-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh">
      <Sidebar />
      <div className="floodlight flex min-w-0 flex-1 flex-col">
        <TopBar />
        {/* On phones the bottom bar covers the last 4rem: leave room for it. */}
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 pt-8 pb-28 lg:px-8 lg:py-10">
          {children}
        </main>
        <BottomNav />
      </div>
    </div>
  );
}
