"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useLayoutEffect, useSyncExternalStore } from "react";

import {
  applyTheme,
  parsePreference,
  preferenceFromCookie,
  resolveTheme,
  storePreference,
  type ThemePreference,
} from "@/lib/theme";
import { cn } from "@/lib/utils";

const CHANGE = "criciq-theme-change";
const DARK_QUERY = "(prefers-color-scheme: dark)";

const OPTIONS: { value: ThemePreference; label: string; Icon: typeof Sun }[] = [
  { value: "system", label: "System theme", Icon: Monitor },
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "dark", label: "Dark theme", Icon: Moon },
];

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia(DARK_QUERY);
  window.addEventListener(CHANGE, onChange);
  media.addEventListener("change", onChange);
  return () => {
    window.removeEventListener(CHANGE, onChange);
    media.removeEventListener("change", onChange);
  };
}

const currentPreference = () => parsePreference(document.documentElement.dataset.themePreference);

function setPreference(preference: ThemePreference): void {
  storePreference(preference);
  const apply = () =>
    applyTheme(resolveTheme(preference, window.matchMedia(DARK_QUERY).matches), preference);
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // A cross-fade between the two themes where the browser can, instead of every colour animating.
  if (!calm && "startViewTransition" in document) document.startViewTransition(apply);
  else apply();
  window.dispatchEvent(new Event(CHANGE));
}

/** System, light or dark, remembered in a cookie the <head> script reads before the first paint. */
export function ThemeToggle({ className }: { className?: string }) {
  // On the server the preference is unknown, so no option is marked until hydration.
  const preference = useSyncExternalStore(subscribe, currentPreference, () => null);

  useLayoutEffect(() => {
    // React's development remount resets <html>; the cookie is the source of truth. A system
    // preference also follows the operating system when it switches while the page is open.
    const sync = () => {
      const stored = preferenceFromCookie(document.cookie);
      applyTheme(resolveTheme(stored, window.matchMedia(DARK_QUERY).matches), stored);
    };
    sync();
    const media = window.matchMedia(DARK_QUERY);
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  // Arrow keys move the choice, as in any radio group; only the chosen option is a tab stop.
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const index = OPTIONS.findIndex((o) => o.value === (preference ?? "system"));
    const next = (index + step + OPTIONS.length) % OPTIONS.length;
    setPreference(OPTIONS[next].value);
    event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=radio]")[next]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      onKeyDown={onKeyDown}
      className={cn("inline-flex items-center gap-0.5 rounded-lg bg-muted p-0.5", className)}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const checked = preference === value;
        const tabbable = preference === null ? value === "system" : checked;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={label}
            title={label}
            tabIndex={tabbable ? 0 : -1}
            onClick={() => setPreference(value)}
            className={cn(
              "inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50",
              checked && "bg-background text-foreground shadow-elev-1",
            )}
          >
            <Icon className="size-3.5" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
