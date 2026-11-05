/**
 * Records hub helpers: the record groups, the page's URL filters (checked before they reach
 * the API), paging, and how an entry's people, sides and match read and link.
 */

import type { RecordCategory, RecordEntry } from "@/lib/api/types";
import type { MatchFormat } from "@/lib/competitions";
import KEYS from "@/lib/record-keys.json";

export const GROUP_LABELS: Record<RecordCategory, string> = {
  batting: "Batting",
  bowling: "Bowling",
  fielding: "Fielding",
  seasons: "Seasons",
  partnerships: "Partnerships",
  teams: "Teams",
  ball_by_ball: "Ball by ball",
};

/** Records only ball-by-ball data can give, said under that group's heading. */
export const BALL_BY_BALL_NOTE =
  "Only ball-by-ball data can give these: runs off one over, and the moments and players that moved a side's chance of winning the most.";

/** The record keys a format has (the sitemap's record pages). */
export function recordKeys(format: MatchFormat): string[] {
  return (KEYS as Record<MatchFormat, string[]>)[format] ?? [];
}

/** Entries per page of a record's list. */
export const PAGE_SIZE = 50;

type Raw = Record<string, string | string[] | undefined>;

function one(raw: Raw, key: string): string | undefined {
  const value = raw[key];
  return Array.isArray(value) ? value[0] : value;
}

function int(value: string | undefined, min: number, max: number): number | undefined {
  if (value === undefined || !/^\d+$/.test(value)) return undefined;
  const n = Number(value);
  return n >= min && n <= max ? n : undefined;
}

/** The page number in the URL (1 when missing or malformed). */
export function pageOf(raw: Raw): number {
  return int(one(raw, "page"), 1, 2000) ?? 1;
}

/**
 * The API query for a record page's search params: seasons (``from``, ``to``), ``team``,
 * ``opponent``, ``venue``, ``wicket`` (partnerships) and ``page``. Anything malformed is
 * dropped, so a bad link shows the whole list.
 */
export function recordQuery(raw: Raw, { wicket }: { wicket: boolean }): URLSearchParams {
  const query = new URLSearchParams();
  const from = int(one(raw, "from"), 2000, 2100);
  const to = int(one(raw, "to"), 2000, 2100);
  if (from !== undefined && (to === undefined || from <= to)) query.set("from", String(from));
  if (to !== undefined && (from === undefined || from <= to)) query.set("to", String(to));
  for (const key of ["team", "opponent"]) {
    const value = one(raw, key);
    if (value && /^[A-Za-z0-9]{2,8}$/.test(value)) query.set(key, value);
  }
  const venue = one(raw, "venue");
  if (venue && venue.length <= 80) query.set("venue", venue);
  if (wicket) {
    const w = int(one(raw, "wicket"), 1, 10);
    if (w !== undefined) query.set("wicket", String(w));
  }
  query.set("limit", String(PAGE_SIZE));
  const page = pageOf(raw);
  if (page > 1) query.set("offset", String((page - 1) * PAGE_SIZE));
  return query;
}

/** "Rahul Tripathi (batting), R Ashwin (bowling)", "Gayle & Samuels", or the side. */
export function whoLabel(entry: RecordEntry): string {
  if (entry.players.length === 0) return entry.team?.name ?? "—";
  const roles = entry.players.map((p) =>
    p.role ? `${p.name} (${p.role === "batter" ? "batting" : "bowling"})` : p.name,
  );
  return entry.players.some((p) => p.role) ? roles.join(", ") : roles.join(" & ");
}

/** The match page, opened at the record's ball where it has one. */
export function matchHref(entry: RecordEntry): string | null {
  if (entry.match_id === null || entry.match_id === undefined) return null;
  return `/matches/${entry.match_id}${entry.ball ? `?ball=${entry.ball}` : ""}`;
}

/** "5 Nov 2023". */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  const month = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ][m - 1];
  return `${d} ${month} ${y}`;
}
