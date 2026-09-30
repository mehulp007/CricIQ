import { cn } from "@/lib/utils";

/** Relative luminance of a #rrggbb colour (WCAG formula). */
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Franchise identity: a small colour swatch plus the short name. Colour is
 * an accent only; the text always carries the identity. Very dark franchise
 * colours get a brighter outline so the swatch stays visible on dark surfaces.
 */
export function TeamSwatch({ color, className }: { color: string; className?: string }) {
  const dark = /^#[0-9a-f]{6}$/i.test(color) && luminance(color) < 0.05;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-2.5 shrink-0 rounded-full ring-1",
        dark ? "ring-white/60" : "ring-white/20",
        className,
      )}
      style={{ backgroundColor: color }}
    />
  );
}

export function TeamBadge({
  shortName,
  color,
  className,
}: {
  shortName: string;
  color: string;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-mono text-xs font-medium", className)}>
      <TeamSwatch color={color} />
      {shortName}
    </span>
  );
}
