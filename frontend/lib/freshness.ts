import type { Meta } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

/** "2008–2027" from the seasons the data holds, or null without any. */
export function seasonSpan(meta: Pick<Meta, "seasons">): string | null {
  const years = meta.seasons.map((s) => s.year);
  if (years.length === 0) return null;
  return `${Math.min(...years)}–${Math.max(...years)}`;
}

function count(n: number, one: string, many: string): string {
  return `${n.toLocaleString("en-IN")} ${n === 1 ? one : many}`;
}

/**
 * The top bar's freshness note: what the latest data sync brought, or how far
 * the data reaches when nothing has been synced since the first load.
 */
export function freshnessLabel(
  meta: Pick<Meta, "last_update" | "latest_match_date">,
): string | null {
  const update = meta.last_update;
  if (update) {
    const parts = [`Data updated ${formatDate(update.updated_at.slice(0, 10))}`];
    if (update.new_matches > 0) parts.push(count(update.new_matches, "new match", "new matches"));
    if (update.corrected_matches > 0) parts.push(`${update.corrected_matches} corrected`);
    if (update.withdrawn_matches > 0) parts.push(`${update.withdrawn_matches} withdrawn`);
    return parts.join(" · ");
  }
  if (meta.latest_match_date) return `Data to ${formatDate(meta.latest_match_date)}`;
  return null;
}

type Freshness = Pick<Meta, "last_update" | "latest_match_date">;

/**
 * Every competition's freshness as one: a sync updates them together, so the
 * newest update's matches are added up across the competitions it touched.
 */
export function combinedFreshness(metas: Freshness[]): Freshness {
  const updates = metas.flatMap((m) => (m.last_update ? [m.last_update] : []));
  const latest = updates
    .map((u) => u.updated_at)
    .sort()
    .at(-1);
  const dates = metas.flatMap((m) => (m.latest_match_date ? [m.latest_match_date] : []));
  const sameRun = updates.filter((u) => u.updated_at === latest);
  return {
    latest_match_date: dates.sort().at(-1) ?? null,
    last_update: latest
      ? {
          updated_at: latest,
          new_matches: sameRun.reduce((n, u) => n + u.new_matches, 0),
          corrected_matches: sameRun.reduce((n, u) => n + u.corrected_matches, 0),
          withdrawn_matches: sameRun.reduce((n, u) => n + u.withdrawn_matches, 0),
        }
      : null,
  };
}
