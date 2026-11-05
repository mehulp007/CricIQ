/**
 * Looks for the exportable charts. ``site`` follows the page's light or dark theme
 * through CSS variables (resolved to colours when exported); the others are fixed
 * palettes, so an exported image looks the same wherever it is opened.
 */

export type ChartThemeName = "site" | "dark" | "light" | "navy" | "paper";

export interface ChartTheme {
  name: ChartThemeName;
  label: string;
  background: string;
  foreground: string;
  muted: string;
  grid: string;
  /** Series colours, in order; the first is replaced by a chosen accent. */
  series: readonly string[];
}

const font = (family: string) => `var(${family}), ui-sans-serif, system-ui, sans-serif`;

export const FONTS = {
  heading: font("--font-sora"),
  body: font("--font-geist-sans"),
  mono: "var(--font-geist-mono), ui-monospace, monospace",
} as const;

export const CHART_THEMES: Record<ChartThemeName, ChartTheme> = {
  site: {
    name: "site",
    label: "Site",
    background: "var(--card)",
    foreground: "var(--foreground)",
    muted: "var(--muted-foreground)",
    grid: "var(--border)",
    series: [
      "var(--chart-1)",
      "var(--chart-2)",
      "var(--chart-3)",
      "var(--chart-4)",
      "var(--chart-5)",
    ],
  },
  dark: {
    name: "dark",
    label: "Dark",
    background: "#0b0f17",
    foreground: "#e7ecf3",
    muted: "#8b97a8",
    grid: "#1f2937",
    series: ["#00e5a0", "#38bdf8", "#f59e0b", "#f472b6", "#a78bfa", "#94a3b8"],
  },
  light: {
    name: "light",
    label: "Light",
    background: "#ffffff",
    foreground: "#111827",
    muted: "#6b7280",
    grid: "#e5e7eb",
    series: ["#0f9d73", "#0284c7", "#d97706", "#db2777", "#7c3aed", "#475569"],
  },
  navy: {
    name: "navy",
    label: "Navy",
    background: "#0a1931",
    foreground: "#f1f5f9",
    muted: "#9fb3cc",
    grid: "#1d3557",
    series: ["#ffd166", "#06d6a0", "#4cc9f0", "#ef476f", "#c3a6ff", "#a8b8cc"],
  },
  paper: {
    name: "paper",
    label: "Paper",
    background: "#f7f3ea",
    foreground: "#22201c",
    muted: "#6f685c",
    grid: "#e2dccd",
    series: ["#b5442c", "#2f6f8f", "#c08a1e", "#4e7d4b", "#7a4f8f", "#5d5a52"],
  },
};

/** The theme with ``accent`` as its first series colour. */
export function chartTheme(name: ChartThemeName, accent?: string | null): ChartTheme {
  const base = CHART_THEMES[name];
  if (!accent) return base;
  return { ...base, series: [accent, ...base.series.slice(1)] };
}

export type ChartSizeName = "landscape" | "square" | "portrait";

export const CHART_SIZES: Record<ChartSizeName, { label: string; width: number; height: number }> =
  {
    landscape: { label: "Landscape 1200 × 675", width: 1200, height: 675 },
    square: { label: "Square 1080 × 1080", width: 1080, height: 1080 },
    portrait: { label: "Portrait 1080 × 1920", width: 1080, height: 1920 },
  };
