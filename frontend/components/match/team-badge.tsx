import { cn } from "@/lib/utils";

/** Relative luminance of a #rrggbb colour (WCAG formula). */
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Franchise identity: a small colour swatch plus the short name. Colour is
 * an accent only; the text always carries the identity. The outline keeps the
 * swatch visible on either theme: very dark colours get a bright one on dark
 * surfaces, very pale colours a dark one on light surfaces.
 */
export function TeamSwatch({ color, className }: { color: string; className?: string }) {
  const lum = /^#[0-9a-f]{6}$/i.test(color) ? luminance(color) : 0.3;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-2.5 shrink-0 rounded-full ring-1",
        lum > 0.6 ? "ring-foreground/45" : "ring-foreground/15",
        lum < 0.05 ? "dark:ring-white/60" : "dark:ring-white/20",
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
