/**
 * Compare page helpers: URL state, which role to compare, side-by-side rows
 * and season-by-season series. Both players are always measured over the
 * same seasons and against par, so eras and roles compare fairly.
 */
import type { PlayerProfile, Rating, RatingGroup } from "@/lib/api/types";
import { isCompetitionId, type CompetitionId } from "@/lib/competitions";
import { parsePlayerId } from "@/lib/matchups";
import { parseSeason, rate, signed } from "@/lib/players";

export type CompareRole = "batting" | "bowling";

/** Player A in the blue team colour, player B in orange: a colour-blind-safe pair. */
export const COMPARE_SERIES = {
  a: { color: "var(--chart-1)" },
  b: { color: "var(--chart-2)" },
} as const;

export interface CompareState {
  a?: string;
  b?: string;
  from?: number;
  to?: number;
  role?: CompareRole;
  /** Each player's competition when it is not the page's: compare across formats. */
  af?: CompetitionId;
  bf?: CompetitionId;
}

function competitionParam(raw: string | string[] | undefined): CompetitionId | undefined {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return isCompetitionId(value) ? value : undefined;
}

type Params = Record<string, string | string[] | undefined>;

export function parseCompare(raw: Params): CompareState {
  const from = parseSeason(raw.from);
  const to = parseSeason(raw.to);
  const role = Array.isArray(raw.role) ? raw.role[0] : raw.role;
  const [low, high] = from && to && from > to ? [to, from] : [from, to];
  return {
    a: parsePlayerId(raw.a),
    b: parsePlayerId(raw.b),
    from: low,
    to: high,
    role: role === "batting" || role === "bowling" ? role : undefined,
    af: competitionParam(raw.af),
    bf: competitionParam(raw.bf),
  };
}

export function compareHref(
  a: string | undefined,
  b: string | undefined,
  rest: Omit<CompareState, "a" | "b"> = {},
): string {
  const params = new URLSearchParams();
  if (a) params.set("a", a);
  if (b) params.set("b", b);
  if (rest.from) params.set("from", String(rest.from));
  if (rest.to) params.set("to", String(rest.to));
  if (rest.role) params.set("role", rest.role);
  if (rest.af) params.set("af", rest.af);
  if (rest.bf) params.set("bf", rest.bf);
  const query = params.toString();
  return query ? `/compare?${query}` : "/compare";
}

export function hasRole(profile: PlayerProfile, role: CompareRole): boolean {
  const summary = role === "batting" ? profile.batting : profile.bowling;
  return summary !== null && summary !== undefined && summary.balls > 0;
}

/** Roles both players have in the window, and the one to show first. */
export function compareRoles(
  a: PlayerProfile,
  b: PlayerProfile,
  wanted?: CompareRole,
): { roles: CompareRole[]; role: CompareRole | null } {
  const roles = (["batting", "bowling"] as const).filter((r) => hasRole(a, r) && hasRole(b, r));
  if (wanted && roles.includes(wanted)) return { roles, role: wanted };
  const bothBowl = a.player.role === "bowler" && b.player.role === "bowler";
  const role = bothBowl && roles.includes("bowling") ? "bowling" : (roles[0] ?? null);
  return { roles, role };
}

// --------------------------------------------------------------------------- headline rows

export interface CompareRow {
  label: string;
  a: string;
  b: string;
  /** Which side the row favours; null when equal, not comparable or not a "better" measure. */
  better: "a" | "b" | null;
  hint?: string;
}

function row(
  label: string,
  a: number | null | undefined,
  b: number | null | undefined,
  format: (v: number) => string,
  direction: 1 | -1 | 0,
  hint?: string,
): CompareRow {
  const show = (v: number | null | undefined) =>
    v === null || v === undefined || !Number.isFinite(v) ? "—" : format(v);
  let better: CompareRow["better"] = null;
  if (direction !== 0 && a !== null && a !== undefined && b !== null && b !== undefined) {
    const diff = (a - b) * direction;
    if (format(a) !== format(b)) better = diff > 0 ? "a" : diff < 0 ? "b" : null;
  }
  return { label, a: show(a), b: show(b), better, hint };
}

const whole = (v: number) => Math.round(v).toLocaleString("en-IN");

export function headlineRows(a: PlayerProfile, b: PlayerProfile, role: CompareRole): CompareRow[] {
  if (role === "batting") {
    const x = a.batting!;
    const y = b.batting!;
    const per100 = (s: typeof x) => (s.balls ? (100 * s.runs_above_par) / s.balls : null);
    return [
      row("Innings", x.innings, y.innings, whole, 0),
      row("Runs", x.runs, y.runs, whole, 0),
      row("Average", x.average, y.average, (v) => rate(v), 1),
      row("Strike rate", x.strike_rate, y.strike_rate, (v) => rate(v), 1),
      row(
        "Par strike rate",
        x.par_strike_rate,
        y.par_strike_rate,
        (v) => rate(v),
        0,
        "What an average batter would have scored from the same balls",
      ),
      row("Runs above par per 100 balls", per100(x), per100(y), (v) => signed(v), 1),
      row("Runs above par", x.runs_above_par, y.runs_above_par, (v) => signed(v, 0), 1),
      row("Boundary %", x.boundary_pct, y.boundary_pct, (v) => rate(v, 1), 0),
      row("Dot ball %", x.dot_pct, y.dot_pct, (v) => rate(v, 1), 0),
      {
        label: "50s / 100s",
        a: `${x.fifties} / ${x.hundreds}`,
        b: `${y.fifties} / ${y.hundreds}`,
        better: null,
      },
      row(
        "Win probability added",
        x.wpa,
        y.wpa,
        (v) => signed(v, 2),
        1,
        "In wins: the sum of every change in the team's chance of winning on the player's balls",
      ),
    ];
  }
  const x = a.bowling!;
  const y = b.bowling!;
  const per24 = (s: typeof x) => (s.balls ? (6 * s.runs_saved) / s.balls : null);
  return [
    row("Innings", x.innings, y.innings, whole, 0),
    row("Overs", x.balls, y.balls, (v) => `${Math.floor(v / 6)}.${v % 6}`, 0),
    row("Wickets", x.wickets, y.wickets, whole, 0),
    row("Economy", x.economy, y.economy, (v) => rate(v), -1),
    row(
      "Par economy",
      x.par_economy,
      y.par_economy,
      (v) => rate(v),
      0,
      "What an average bowler would have conceded from the same balls",
    ),
    row("Runs saved per over", per24(x), per24(y), (v) => signed(v, 2), 1),
    row("Runs saved vs par", x.runs_saved, y.runs_saved, (v) => signed(v, 0), 1),
    row("Strike rate", x.strike_rate, y.strike_rate, (v) => rate(v, 1), -1, "Balls per wicket"),
    row("Average", x.average, y.average, (v) => rate(v, 1), -1),
    row("Dot ball %", x.dot_pct, y.dot_pct, (v) => rate(v, 1), 1),
    row(
      "Win probability added",
      x.wpa,
      y.wpa,
      (v) => signed(v, 2),
      1,
      "In wins: the sum of every change in the team's chance of winning on the player's balls",
    ),
  ];
}

// --------------------------------------------------------------------------- ratings

export interface RatingPair {
  key: string;
  label: string;
  description: string;
  a: Rating | null;
  b: Rating | null;
}

/** Both players' ratings, row by row in the API's order. */
export function ratingPairs(
  a: RatingGroup | null | undefined,
  b: RatingGroup | null | undefined,
  sharedOnly = false,
): RatingPair[] {
  const rows = new Map<string, RatingPair>();
  for (const [side, group] of [
    ["a", a],
    ["b", b],
  ] as const) {
    for (const item of group?.items ?? []) {
      const found = rows.get(item.key) ?? {
        key: item.key,
        label: item.label,
        description: item.description,
        a: null,
        b: null,
      };
      found[side] = item;
      rows.set(item.key, found);
    }
  }
  // Across formats only the skills both rate line up (a Test has no death overs).
  return [...rows.values()].filter((r) => !sharedOnly || (r.a !== null && r.b !== null));
}

// --------------------------------------------------------------------------- seasons

export type Align = "season" | "age";

export interface TrendPoint {
  x: number;
  a: number | null;
  b: number | null;
  aBalls: number;
  bBalls: number;
  aSeason?: number;
  bSeason?: number;
}

/** Seasons with fewer balls than this are left out of the trend: too noisy to plot. */
export const TREND_MIN_BALLS = 30;

/** Age on 1 May of a season (IPL seasons run from late March to early June). */
export function ageInSeason(dateOfBirth: string | null | undefined, season: number): number | null {
  if (!dateOfBirth) return null;
  const [y, m, d] = dateOfBirth.split("-").map(Number);
  if (!y) return null;
  return season - y - (m > 5 || (m === 5 && d > 1) ? 1 : 0);
}

function seasonValues(
  profile: PlayerProfile,
  role: CompareRole,
): { season: number; value: number; balls: number }[] {
  return profile.seasons.flatMap((s) => {
    if (role === "batting") {
      const b = s.batting;
      if (
        !b ||
        b.balls < TREND_MIN_BALLS ||
        b.strike_rate === null ||
        b.strike_rate === undefined ||
        b.par_strike_rate === null ||
        b.par_strike_rate === undefined
      )
        return [];
      return [{ season: s.season, value: b.strike_rate - b.par_strike_rate, balls: b.balls }];
    }
    const b = s.bowling;
    if (
      !b ||
      b.balls < TREND_MIN_BALLS ||
      b.economy === null ||
      b.economy === undefined ||
      b.par_economy === null ||
      b.par_economy === undefined
    )
      return [];
    return [{ season: s.season, value: b.par_economy - b.economy, balls: b.balls }];
  });
}

/**
 * Runs above par per 100 balls (batting) or runs saved per over (bowling),
 * season by season or by age, one row per x with both players.
 */
export function trend(
  a: PlayerProfile,
  b: PlayerProfile,
  role: CompareRole,
  align: Align,
): TrendPoint[] {
  const points = new Map<number, TrendPoint>();
  for (const [side, profile] of [
    ["a", a],
    ["b", b],
  ] as const) {
    for (const v of seasonValues(profile, role)) {
      const x = align === "season" ? v.season : ageInSeason(profile.player.date_of_birth, v.season);
      if (x === null) continue;
      const point = points.get(x) ?? { x, a: null, b: null, aBalls: 0, bBalls: 0 };
      point[side] = Math.round(v.value * 100) / 100;
      if (side === "a") {
        point.aBalls = v.balls;
        point.aSeason = v.season;
      } else {
        point.bBalls = v.balls;
        point.bSeason = v.season;
      }
      points.set(x, point);
    }
  }
  return [...points.values()].sort((p, q) => p.x - q.x);
}
