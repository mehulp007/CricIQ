import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "@/components/theme/theme-toggle";
import { THEME_COOKIE } from "@/lib/theme";

beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("dark"),
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = `${THEME_COOKIE}=; max-age=0; path=/`;
  document.documentElement.className = "";
  delete document.documentElement.dataset.themePreference;
});

describe("ThemeToggle", () => {
  it("offers system, light and dark as one radio group", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("radiogroup", { name: "Theme" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
  });

  it("starts from the stored preference", () => {
    document.cookie = `${THEME_COOKIE}=light; path=/`;
    render(<ThemeToggle />);
    expect(screen.getByRole("radio", { name: "Light theme" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("switches the theme, remembers it, and moves with the arrow keys", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Dark theme" }));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.cookie).toContain(`${THEME_COOKIE}=dark`);
    expect(screen.getByRole("radio", { name: "Dark theme" })).toHaveAttribute("tabindex", "0");

    fireEvent.keyDown(screen.getByRole("radiogroup"), { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "System theme" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("radio", { name: "System theme" })).toHaveFocus();
  });
});
