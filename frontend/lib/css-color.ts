/**
 * A theme token (`--team-a`) as `rgb(r, g, b)`, for three.js, which reads neither CSS variables
 * nor oklch(). The browser converts it by painting one pixel. Client only.
 */
let canvas: HTMLCanvasElement | null = null;

export function tokenColor(name: string, fallback = "#888888"): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!value) return fallback;
  canvas ??= document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const g = canvas.getContext("2d", { willReadFrequently: true });
  if (!g) return fallback;
  g.clearRect(0, 0, 1, 1);
  g.fillStyle = fallback;
  g.fillStyle = value;
  g.fillRect(0, 0, 1, 1);
  const [r, gr, b] = g.getImageData(0, 0, 1, 1).data;
  return `rgb(${r}, ${gr}, ${b})`;
}
