/**
 * Props for a horizontally scrollable wrapper (e.g. a wide table on a phone):
 * keyboard users can focus it and scroll with the arrow keys, and screen
 * readers announce what it contains.
 */
export function scrollRegion(label: string) {
  return { role: "region", "aria-label": label, tabIndex: 0 } as const;
}
