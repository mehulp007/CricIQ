/**
 * Chart styling from the design tokens, so every chart follows the light and dark themes.
 * Recharts takes these as props; the CSS variables resolve against the current theme.
 */

/** Axis line and tick labels. */
export const AXIS = {
  stroke: "var(--border)",
  tick: { fill: "var(--muted-foreground)", fontSize: 11 },
} as const;

/** Recharts' built-in tooltip box. */
export const TOOLTIP_STYLE = {
  background: "var(--popover)",
  color: "var(--popover-foreground)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
  boxShadow: "var(--elevation-2)",
} as const;
