/**
 * Light and dark themes. The preference (system, light or dark) lives in a cookie that an inline
 * script in <head> reads before the first paint, so every page stays statically prerendered and
 * never flashes the wrong theme. Reading the cookie on the server would make every page dynamic.
 */

export const THEME_COOKIE = "criciq-theme";
export const PREFERENCES = ["system", "light", "dark"] as const;
export type ThemePreference = (typeof PREFERENCES)[number];
export type Theme = "light" | "dark";

const ONE_YEAR = 60 * 60 * 24 * 365;

export function parsePreference(value: string | null | undefined): ThemePreference {
  return PREFERENCES.includes(value as ThemePreference) ? (value as ThemePreference) : "system";
}

export function preferenceFromCookie(cookie: string): ThemePreference {
  const match = cookie.match(new RegExp(`(?:^|; )${THEME_COOKIE}=([^;]*)`));
  return parsePreference(match ? decodeURIComponent(match[1]) : null);
}

export function resolveTheme(preference: ThemePreference, systemDark: boolean): Theme {
  if (preference === "system") return systemDark ? "dark" : "light";
  return preference;
}

/** Put a theme on <html>: the `dark` class the styles key off, and the browser's colour scheme. */
export function applyTheme(theme: Theme, preference: ThemePreference): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
  root.dataset.themePreference = preference;
}

export function storePreference(preference: ThemePreference): void {
  document.cookie = `${THEME_COOKIE}=${preference}; path=/; max-age=${ONE_YEAR}; SameSite=Lax`;
}

/**
 * The inline <head> script: the same steps as preferenceFromCookie, resolveTheme and applyTheme,
 * written out because it runs before any JavaScript bundle has loaded.
 */
export const THEME_SCRIPT = `(function(){try{var m=document.cookie.match(/(?:^|; )${THEME_COOKIE}=([^;]*)/);var p=m?decodeURIComponent(m[1]):"system";if(p!=="light"&&p!=="dark")p="system";var t=p==="system"?(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):p;var r=document.documentElement;r.classList.toggle("dark",t==="dark");r.style.colorScheme=t;r.dataset.themePreference=p}catch(e){}})()`;
