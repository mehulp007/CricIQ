/**
 * Scale maths for the exportable SVG charts (components/charts/svg): nice axis ticks,
 * linear scales, figure formatting and fitting text into a width without a DOM.
 */

/** Round-number ticks covering ``[min, max]`` (about ``count`` of them), from zero up. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  const lo = Math.min(0, min);
  const hi = Math.max(0, max);
  if (hi === lo) return [lo];
  const raw = (hi - lo) / Math.max(1, count);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  const first = Math.floor(lo / step) * step;
  const last = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let i = 0, v = first; v <= last + step / 2; i += 1, v = first + i * step) {
    ticks.push(Number(v.toPrecision(12)));
  }
  return ticks;
}

/** A linear map from a domain to a range (a flat domain maps to the range's start). */
export function linear(
  [d0, d1]: readonly [number, number],
  [r0, r1]: readonly [number, number],
): (value: number) => number {
  if (d1 === d0) return () => r0;
  return (value) => r0 + ((value - d0) / (d1 - d0)) * (r1 - r0);
}

/** A figure with grouping commas and at most ``digits`` decimals ("—" for none). */
export function formatFigure(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US", { maximumFractionDigits: digits });
}

// Average glyph width as a share of the font size (a proportional sans).
const GLYPH = 0.56;

/** About how wide ``text`` sets at ``fontSize`` px. */
export function textWidth(text: string, fontSize: number): number {
  return text.length * fontSize * GLYPH;
}

/** ``text`` cut to fit ``maxWidth`` px at ``fontSize``, ending in "…" when cut. */
export function fitText(text: string, maxWidth: number, fontSize: number): string {
  if (textWidth(text, fontSize) <= maxWidth) return text;
  const chars = Math.max(1, Math.floor(maxWidth / (fontSize * GLYPH)) - 1);
  return `${text.slice(0, chars).trimEnd()}…`;
}
