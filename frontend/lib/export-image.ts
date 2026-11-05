/**
 * Save a chart as an SVG or PNG file, or its figures as CSV, with browser APIs only.
 *
 * An exported SVG has to stand alone: the page's CSS variables are resolved to the
 * colours they have now, and the fonts it uses are embedded as data URIs (an image
 * drawn onto a canvas can't fetch fonts of its own). The PNG is that SVG drawn onto a
 * canvas at the chart's export size.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

/** A safe file name: "Virat Kohli: runs by format" -> "virat-kohli-runs-by-format". */
export function fileName(title: string, extension: string): string {
  const stem =
    title
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80) || "criciq-chart";
  return `${stem}.${extension}`;
}

/** One CSV cell: quoted when needed, and never read as a spreadsheet formula. */
export function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  let text = String(value);
  if (/^[=+\-@\t\r]/.test(text) && !/^-?\d+(\.\d+)?$/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Rows as CSV text, headers first, with Windows line endings (what spreadsheets expect). */
export function toCsv(headers: string[], rows: unknown[][]): string {
  return [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

/** Replace every ``var(--name)`` in ``text`` with its current value (``fallback`` if unset). */
export function resolveVariables(
  text: string,
  lookup: (name: string) => string,
  fallback = "#888888",
): string {
  return text.replace(/var\((--[\w-]+)\)/g, (_, name: string) => lookup(name).trim() || fallback);
}

/** Every family a CSS ``font-family`` value names, unquoted ("'Geist', sans-serif" -> Geist, sans-serif). */
export function fontFamilies(value: string): string[] {
  return value
    .split(",")
    .map((f) => f.trim().replace(/^['"]|['"]$/g, ""))
    .filter(Boolean);
}

async function dataUrl(url: string): Promise<string | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const blob = await response.blob();
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : null);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

/** ``@font-face`` rules for the given families, with their files inlined. */
async function embeddedFonts(families: Set<string>): Promise<string> {
  const rules: CSSFontFaceRule[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let list: CSSRuleList;
    try {
      list = sheet.cssRules;
    } catch {
      continue; // another origin's stylesheet
    }
    for (const rule of Array.from(list)) {
      if (rule instanceof CSSFontFaceRule) {
        const family = fontFamilies(rule.style.getPropertyValue("font-family"))[0];
        if (family && families.has(family)) rules.push(rule);
      }
    }
  }
  const css = await Promise.all(
    rules.map(async (rule) => {
      const src = rule.style.getPropertyValue("src");
      const match = /url\(["']?([^"')]+)["']?\)/.exec(src);
      if (!match) return "";
      const inlined = await dataUrl(new URL(match[1], document.baseURI).href);
      if (!inlined) return "";
      return rule.cssText.replace(src, `url(${inlined})`);
    }),
  );
  return css.filter(Boolean).join("\n");
}

/** The chart as a standalone SVG document at its export size. */
export async function svgDocument(svg: SVGSVGElement): Promise<string> {
  const width = svg.dataset.exportWidth ?? String(svg.viewBox.baseVal.width);
  const height = svg.dataset.exportHeight ?? String(svg.viewBox.baseVal.height);
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", SVG_NS);
  clone.setAttribute("width", width);
  clone.setAttribute("height", height);
  clone.removeAttribute("style");
  clone.removeAttribute("class");

  const root = getComputedStyle(document.documentElement);
  const markup = resolveVariables(new XMLSerializer().serializeToString(clone), (name) =>
    root.getPropertyValue(name),
  );

  const families = new Set<string>();
  for (const match of markup.matchAll(/font-family="([^"]+)"/g)) {
    for (const family of fontFamilies(match[1].replace(/&quot;/g, '"'))) families.add(family);
  }
  const fonts = await embeddedFonts(families);
  if (!fonts) return markup;
  const style = `<defs><style>${fonts.replace(/]]>/g, "")}</style></defs>`;
  return markup.replace(/(<svg[^>]*>)/, `$1${style}`);
}

/** Start a download of ``blob`` as ``name``. */
export function download(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadSvg(svg: SVGSVGElement, title: string): Promise<void> {
  const markup = await svgDocument(svg);
  download(new Blob([markup], { type: "image/svg+xml;charset=utf-8" }), fileName(title, "svg"));
}

/** The chart as a PNG at its export size (``scale`` 2 for a sharper image). */
export async function pngBlob(svg: SVGSVGElement, scale = 1): Promise<Blob> {
  await document.fonts.ready;
  const markup = await svgDocument(svg);
  const width = Number(svg.dataset.exportWidth ?? svg.viewBox.baseVal.width);
  const height = Number(svg.dataset.exportHeight ?? svg.viewBox.baseVal.height);
  const url = URL.createObjectURL(new Blob([markup], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    image.decoding = "async";
    image.src = url;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("this browser can't draw images");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve, reject) =>
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("no image"))), "image/png"),
    );
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function downloadPng(svg: SVGSVGElement, title: string): Promise<void> {
  download(await pngBlob(svg), fileName(title, "png"));
}

export function downloadCsv(headers: string[], rows: unknown[][], title: string): void {
  download(
    new Blob([toCsv(headers, rows)], { type: "text/csv;charset=utf-8" }),
    fileName(title, "csv"),
  );
}
