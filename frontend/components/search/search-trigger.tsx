"use client";

import { Search } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

// The palette's code downloads once the page is idle (or when it first opens), so it is ready by
// the time anyone types into it.
const loadPalette = () => import("@/components/search/command-palette");
const CommandPalette = dynamic(() => loadPalette().then((m) => m.CommandPalette), {
  ssr: false,
});

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return Boolean(
    el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName)),
  );
}

/** Opens the search palette: the button, Ctrl/⌘ K anywhere, or "/" when not typing. */
export function SearchTrigger({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const [used, setUsed] = useState(false);

  useEffect(() => {
    if (!("requestIdleCallback" in window)) return;
    const id = window.requestIdleCallback(() => void loadPalette(), { timeout: 4000 });
    return () => window.cancelIdleCallback(id);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const combo = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      const slash = event.key === "/" && !isTyping(event.target);
      if (combo || slash) {
        event.preventDefault();
        setUsed(true);
        setOpen((o) => (combo ? !o : true));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setUsed(true);
          setOpen(true);
        }}
        aria-keyshortcuts="Control+K Meta+K /"
        className={cn(
          "inline-flex h-8 items-center gap-2 rounded-lg border border-input bg-background/60 px-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
          className,
        )}
      >
        <Search className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">Search</span>
        <span className="sr-only sm:hidden">Search</span>
        <kbd className="ml-4 hidden rounded border border-border px-1.5 font-mono text-[10px] lg:inline">
          Ctrl K
        </kbd>
      </button>
      {used && <CommandPalette open={open} onOpenChange={setOpen} />}
    </>
  );
}
