"use client";

import { useSyncExternalStore } from "react";

import type { Theme } from "@/lib/theme";

function subscribe(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

const current = (): Theme =>
  document.documentElement.classList.contains("dark") ? "dark" : "light";

/** The theme on <html> right now (after the system preference is resolved), kept live. */
export function useResolvedTheme(): Theme {
  return useSyncExternalStore(subscribe, current, () => "dark");
}
