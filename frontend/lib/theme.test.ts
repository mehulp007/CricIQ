import { afterEach, describe, expect, it, vi } from "vitest";

import {
  THEME_COOKIE,
  THEME_SCRIPT,
  applyTheme,
  parsePreference,
  preferenceFromCookie,
  resolveTheme,
} from "@/lib/theme";

function mockSystemDark(dark: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("dark") ? dark : false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = `${THEME_COOKIE}=; max-age=0; path=/`;
  document.documentElement.className = "";
  document.documentElement.removeAttribute("style");
  delete document.documentElement.dataset.themePreference;
});

describe("theme preference", () => {
  it("accepts only system, light or dark", () => {
    expect(parsePreference("light")).toBe("light");
    expect(parsePreference("dark")).toBe("dark");
    expect(parsePreference("purple")).toBe("system");
    expect(parsePreference(null)).toBe("system");
  });

  it("reads the cookie among others", () => {
    expect(preferenceFromCookie(`a=1; ${THEME_COOKIE}=dark; b=2`)).toBe("dark");
    expect(preferenceFromCookie("a=1")).toBe("system");
  });

  it("follows the operating system only for the system preference", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("puts the theme on <html>", () => {
    applyTheme("dark", "system");
    const root = document.documentElement;
    expect(root.classList.contains("dark")).toBe(true);
    expect(root.style.colorScheme).toBe("dark");
    expect(root.dataset.themePreference).toBe("system");
    applyTheme("light", "light");
    expect(root.classList.contains("dark")).toBe(false);
  });
});

describe("the inline <head> script", () => {
  const run = () => new Function(THEME_SCRIPT)();

  it("applies the stored preference", () => {
    mockSystemDark(true);
    document.documentElement.classList.add("dark");
    document.cookie = `${THEME_COOKIE}=light; path=/`;
    run();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.dataset.themePreference).toBe("light");
  });

  it("follows the system without a cookie", () => {
    mockSystemDark(false);
    document.documentElement.classList.add("dark");
    run();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.dataset.themePreference).toBe("system");
    mockSystemDark(true);
    run();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("treats an unknown value as system", () => {
    mockSystemDark(true);
    document.cookie = `${THEME_COOKIE}=neon; path=/`;
    run();
    expect(document.documentElement.dataset.themePreference).toBe("system");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
