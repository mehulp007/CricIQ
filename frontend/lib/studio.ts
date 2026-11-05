/**
 * Chart Studio's state: the spec the API runs, the chart's style, the template it came from
 * and (for a match card) the match. All of it lives in the URL, so a copied link rebuilds
 * the same chart; anything a link gets wrong falls back to the template's defaults.
 */

import type { ChartSizeName, ChartThemeName } from "@/components/charts/svg/theme";
import { CHART_SIZES, CHART_THEMES } from "@/components/charts/svg/theme";
import type {
  StudioDataset,
  StudioOptions,
  StudioResult,
  StudioRow,
  StudioSpec,
} from "@/lib/api/types";

export type ChartType =
  "auto" | "bars" | "grouped" | "multiples" | "columns" | "line" | "table" | "headline";

export const CHART_TYPES: { value: ChartType; label: string }[] = [
  { value: "auto", label: "Automatic" },
  { value: "bars", label: "Bars with figures" },
  { value: "grouped", label: "Grouped bars" },
  { value: "multiples", label: "Small multiples" },
  { value: "columns", label: "Columns" },
  { value: "line", label: "Line" },
  { value: "table", label: "Table" },
  { value: "headline", label: "Headline number" },
];

export const STUDIO_THEMES: ChartThemeName[] = ["dark", "light", "navy", "paper"];

export interface StudioStyle {
  chart: ChartType;
  size: ChartSizeName;
  theme: ChartThemeName;
  /** "#rrggbb", or null for the theme's own. */
  accent: string | null;
  title: string;
  subtitle: string;
  labels: boolean;
}

export const DEFAULT_STYLE: StudioStyle = {
  chart: "auto",
  size: "landscape",
  theme: "dark",
  accent: null,
  title: "",
  subtitle: "",
  labels: true,
};

export type TemplateKey =
  | "profile"
  | "compare"
  | "leaderboard"
  | "timeline"
  | "batting"
  | "bowling"
  | "team-form"
  | "ground"
  | "season"
  | "match"
  | "blank";

export interface StudioState {
  template: TemplateKey;
  spec: StudioSpec;
  style: StudioStyle;
  /** The match card's match. */
  match: number | null;
}

type SpecPart = Partial<Omit<StudioSpec, "filters">> & { filters?: StudioSpec["filters"] };

export interface Template {
  key: TemplateKey;
  label: string;
  description: string;
  spec: (options: StudioOptions) => SpecPart;
  chart: ChartType;
}

const latestSeason = (options: StudioOptions) =>
  options.seasons.length ? Number(options.seasons[options.seasons.length - 1].value) : null;

export const TEMPLATES: Template[] = [
  {
    key: "profile",
    label: "Player profile",
    description: "A career in three numbers (the leading run-scorer until you pick a player).",
    spec: () => ({
      dataset: "careers",
      measures: ["runs", "wickets", "matches"],
      group_by: "player",
      limit: 1,
    }),
    chart: "headline",
  },
  {
    key: "compare",
    label: "Compare players",
    description: "Up to six players side by side, each measure on its own scale.",
    spec: () => ({
      dataset: "batting",
      measures: ["runs", "average", "strike_rate"],
      group_by: "player",
      limit: 6,
    }),
    chart: "grouped",
  },
  {
    key: "leaderboard",
    label: "Leaderboard",
    description: "The top ten by one figure.",
    spec: () => ({ dataset: "batting", measures: ["runs"], group_by: "player", limit: 10 }),
    chart: "bars",
  },
  {
    key: "timeline",
    label: "Timeline",
    description: "Season by season, a line per player.",
    spec: () => ({
      dataset: "batting",
      measures: ["runs"],
      group_by: "season",
      split_by: "player",
      limit: 50,
      series: 4,
    }),
    chart: "line",
  },
  {
    key: "batting",
    label: "Batting explorer",
    description: "Runs, average, strike rate and boundaries for every qualified batter.",
    spec: () => ({
      dataset: "batting",
      measures: ["runs", "average", "strike_rate", "boundary_pct"],
      group_by: "player",
      limit: 25,
    }),
    chart: "table",
  },
  {
    key: "bowling",
    label: "Bowling explorer",
    description: "Wickets, economy, average and dots for every qualified bowler.",
    spec: () => ({
      dataset: "bowling",
      measures: ["wickets", "economy", "average", "dot_pct"],
      group_by: "player",
      limit: 25,
    }),
    chart: "table",
  },
  {
    key: "team-form",
    label: "Team form",
    description: "Each side's win rate season by season.",
    spec: () => ({
      dataset: "teams",
      measures: ["win_pct"],
      group_by: "season",
      split_by: "team",
      limit: 50,
      series: 4,
    }),
    chart: "line",
  },
  {
    key: "ground",
    label: "Grounds",
    description: "How fast batters score at each ground (from the balls bowled there).",
    spec: () => ({
      dataset: "batting",
      measures: ["strike_rate", "runs"],
      group_by: "ground",
      sort: "strike_rate",
      limit: 10,
    }),
    chart: "bars",
  },
  {
    key: "season",
    label: "Season recap",
    description: "The latest season's leading run-scorers, three ways.",
    spec: (options) => {
      const season = latestSeason(options);
      return {
        dataset: "batting",
        measures: ["runs", "sixes", "strike_rate"],
        group_by: "player",
        limit: 8,
        filters: season ? { players: [], season_from: season, season_to: season } : undefined,
      };
    },
    chart: "multiples",
  },
  {
    key: "match",
    label: "Match card",
    description: "A match's scorecard as an image: each innings' total and best performers.",
    spec: () => ({ dataset: "batting", measures: ["runs"], group_by: "player", limit: 1 }),
    chart: "table",
  },
  {
    key: "blank",
    label: "Blank canvas",
    description: "Start from one measure and build your own.",
    spec: () => ({ dataset: "batting", measures: ["runs"], group_by: "player", limit: 15 }),
    chart: "auto",
  },
];

export function template(key: TemplateKey): Template {
  return TEMPLATES.find((t) => t.key === key) ?? TEMPLATES[TEMPLATES.length - 1];
}

function dataset(options: StudioOptions, key: string): StudioDataset | undefined {
  return options.datasets.find((d) => d.key === key);
}

/** A spec made valid for these options: unknown measures, groupings and filters dropped. */
export function normalizeSpec(part: SpecPart, options: StudioOptions): StudioSpec {
  const d = dataset(options, part.dataset ?? "") ?? options.datasets[0];
  const available = new Set(d.measures.map((m) => m.key));
  let measures = [...new Set((part.measures ?? []).filter((m) => available.has(m)))].slice(0, 6);
  if (measures.length === 0) measures = d.default_measures.filter((m) => available.has(m));
  if (measures.length === 0) measures = [d.measures[0].key];

  const dims = new Map(d.dimensions.map((x) => [x.key, x]));
  type Dimension = NonNullable<StudioSpec["group_by"]>;
  const fallback: Dimension = dims.has("player") ? "player" : d.dimensions[0].key;
  let group: Dimension | null =
    part.group_by === null
      ? null
      : part.group_by && dims.has(part.group_by)
        ? part.group_by
        : fallback;
  let split: Dimension | null =
    group !== null && part.split_by && dims.has(part.split_by) && part.split_by !== group
      ? part.split_by
      : null;
  // Careers are a player's: a player is the grouping or the split.
  if (d.needs_player && group !== "player" && split !== "player") {
    if (group === null) group = "player";
    else split = "player";
  }

  const allowed = new Set(d.filters);
  const f = part.filters;
  const teams = new Set(options.teams.map((t) => t.value));
  const grounds = new Set(options.grounds.map((g) => g.value));
  const seasons = new Set(options.seasons.map((s) => Number(s.value)));
  const phases = new Set(options.phases.map((p) => p.value));
  const pick = <T>(name: string, value: T | null | undefined, ok: (v: T) => boolean) =>
    allowed.has(name) && value !== null && value !== undefined && ok(value) ? value : null;
  const players = allowed.has("players")
    ? [...new Set((f?.players ?? []).filter((p) => PLAYER_ID.test(p)))].slice(0, 6)
    : [];
  let from = pick("season", f?.season_from, (v) => seasons.has(v));
  let to = pick("season", f?.season_to, (v) => seasons.has(v));
  if (from !== null && to !== null && from > to) [from, to] = [to, from];
  const filters = {
    players,
    team: pick("team", f?.team, (v) => teams.has(v)),
    opponent: pick("opponent", f?.opponent, (v) => teams.has(v)),
    venue: pick("venue", f?.venue, (v) => grounds.has(v)),
    season_from: from,
    season_to: to,
    position: pick("position", f?.position, (v) => Number.isInteger(v) && v >= 1 && v <= 11),
    innings: pick(
      "innings",
      f?.innings,
      (v) => Number.isInteger(v) && v >= 1 && v <= (d.key === "teams" ? 2 : 4),
    ),
    phase: pick("phase", f?.phase, (v) => phases.has(v)),
  };

  const natural = group !== null && dims.get(group)?.natural;
  let sort = part.sort ?? null;
  if (sort === "group" && !natural) sort = null;
  if (sort !== null && sort !== "group" && !measures.includes(sort)) sort = null;
  return {
    dataset: d.key,
    measures,
    group_by: group,
    split_by: split,
    filters,
    sort,
    order: part.order === "asc" || part.order === "desc" ? part.order : null,
    min_sample: clamp(part.min_sample ?? 0, 0, 1_000_000),
    limit: clamp(part.limit ?? 15, 1, 50),
    series: clamp(part.series ?? MAX_SERIES, 1, MAX_SERIES),
  };
}

export const MAX_SERIES = 8;
const PLAYER_ID = /^[A-Za-z0-9_.-]{1,80}$/;
const HEX = /^[0-9a-fA-F]{6}$/;
const TEXT_MAX = 120;

function clamp(value: number, lo: number, hi: number): number {
  if (!Number.isFinite(value)) return lo;
  return Math.min(hi, Math.max(lo, Math.round(value)));
}

function int(value: string | null): number | null {
  if (value === null || !/^\d+$/.test(value)) return null;
  return Number(value);
}

/** The state a template starts from. */
export function templateState(key: TemplateKey, options: StudioOptions): StudioState {
  const t = template(key);
  return {
    template: t.key,
    spec: normalizeSpec(t.spec(options), options),
    style: { ...DEFAULT_STYLE, chart: t.chart },
    match: null,
  };
}

/** The state a URL describes; anything missing or wrong comes from its template. */
export function parseState(params: URLSearchParams, options: StudioOptions): StudioState {
  const key = (
    TEMPLATES.some((t) => t.key === params.get("t")) ? params.get("t") : "blank"
  ) as TemplateKey;
  const base = templateState(key, options);
  const has = (name: string) => params.has(name);
  const list = (name: string) => (params.get(name) ?? "").split(",").filter(Boolean);
  const group = params.get("g");
  const spec = normalizeSpec(
    {
      dataset: (params.get("d") ?? base.spec.dataset) as StudioSpec["dataset"],
      measures: has("m") ? list("m") : base.spec.measures,
      group_by: has("g")
        ? group === "none"
          ? null
          : (group as StudioSpec["group_by"])
        : base.spec.group_by,
      split_by: has("s") ? (params.get("s") as StudioSpec["split_by"]) : base.spec.split_by,
      filters: {
        players: list("p"),
        team: params.get("team"),
        opponent: params.get("opp"),
        venue: params.get("venue"),
        season_from: has("from") ? int(params.get("from")) : base.spec.filters?.season_from,
        season_to: has("to") ? int(params.get("to")) : base.spec.filters?.season_to,
        position: int(params.get("pos")),
        innings: int(params.get("inn")),
        phase: params.get("phase"),
      },
      sort: has("sort") ? params.get("sort") : base.spec.sort,
      order: (params.get("order") as StudioSpec["order"]) ?? base.spec.order,
      min_sample: int(params.get("min")) ?? base.spec.min_sample,
      limit: int(params.get("n")) ?? base.spec.limit,
      series: int(params.get("k")) ?? base.spec.series,
    },
    options,
  );
  const chart = params.get("chart");
  const size = params.get("size");
  const theme = params.get("theme");
  const accent = params.get("accent");
  const style: StudioStyle = {
    chart: CHART_TYPES.some((c) => c.value === chart) ? (chart as ChartType) : base.style.chart,
    size: size && size in CHART_SIZES ? (size as ChartSizeName) : DEFAULT_STYLE.size,
    theme: theme && theme in CHART_THEMES ? (theme as ChartThemeName) : DEFAULT_STYLE.theme,
    accent: accent && HEX.test(accent) ? `#${accent.toLowerCase()}` : null,
    title: (params.get("title") ?? "").slice(0, TEXT_MAX),
    subtitle: (params.get("sub") ?? "").slice(0, TEXT_MAX),
    labels: params.get("labels") !== "0",
  };
  const match = key === "match" ? int(params.get("match")) : null;
  return { template: key, spec, style, match };
}

/** The URL search params for a state: only what differs from its template. */
export function stateToParams(state: StudioState, options: StudioOptions): URLSearchParams {
  const params = new URLSearchParams();
  const base = templateState(state.template, options);
  const { spec, style } = state;
  const set = (name: string, value: string | number | null | undefined, fallback?: unknown) => {
    if (value === null || value === undefined || value === "" || value === fallback) return;
    params.set(name, String(value));
  };
  if (state.template !== "blank") params.set("t", state.template);
  set("d", spec.dataset, base.spec.dataset);
  const measures = spec.measures.join(",");
  set("m", measures, base.spec.measures.join(","));
  if (spec.group_by !== base.spec.group_by) params.set("g", spec.group_by ?? "none");
  if (spec.split_by !== base.spec.split_by) params.set("s", spec.split_by ?? "");
  const f = spec.filters ?? { players: [] };
  set("p", (f.players ?? []).join(","));
  set("team", f.team);
  set("opp", f.opponent);
  set("venue", f.venue);
  set("from", f.season_from, base.spec.filters?.season_from);
  set("to", f.season_to, base.spec.filters?.season_to);
  if (f.season_from === null && base.spec.filters?.season_from) params.set("from", "");
  if (f.season_to === null && base.spec.filters?.season_to) params.set("to", "");
  set("pos", f.position);
  set("inn", f.innings);
  set("phase", f.phase);
  if (spec.sort !== base.spec.sort) params.set("sort", spec.sort ?? "");
  set("order", spec.order, base.spec.order);
  set("min", spec.min_sample, base.spec.min_sample);
  set("n", spec.limit, base.spec.limit);
  set("k", spec.series, base.spec.series);
  set("chart", style.chart, base.style.chart);
  set("size", style.size, DEFAULT_STYLE.size);
  set("theme", style.theme, DEFAULT_STYLE.theme);
  set("accent", style.accent?.replace("#", ""));
  set("title", style.title);
  set("sub", style.subtitle);
  if (!style.labels) params.set("labels", "0");
  set("match", state.match);
  return params;
}

/** The chart a result is drawn as: the chosen type, or one that suits its shape. */
export function resolveChart(result: StudioResult, chosen: ChartType): Exclude<ChartType, "auto"> {
  if (chosen !== "auto") return chosen;
  const split = result.spec.split_by !== null && result.spec.split_by !== undefined;
  const natural = ["season", "position", "phase", "innings"].includes(result.spec.group_by ?? "");
  if (result.spec.group_by === null || result.rows.length === 1) return "headline";
  if (split) return natural ? "line" : "grouped";
  if (natural) return result.spec.group_by === "season" ? "line" : "columns";
  if (result.columns.length === 1) return "bars";
  if (result.columns.length <= 3) return "grouped";
  return "table";
}

export function rowLabel(row: StudioRow): string {
  return row.group?.label ?? "All";
}

/** A title for a result, from its first measure and grouping ("Runs by player"). */
export function defaultTitle(result: StudioResult, competition: string): string {
  const measure = result.columns[0]?.label ?? "Figures";
  if (!result.group_label) return `${competition}: ${result.dataset_label.toLowerCase()}`;
  // One player (a profile): their name says it.
  const only = result.rows.length === 1 ? result.rows[0].group : null;
  if (only?.player_id && !result.split_label) return `${only.label} in the ${competition}`;
  const split = result.split_label ? ` and ${result.split_label.toLowerCase()}` : "";
  return `${competition}: ${measure.toLowerCase()} by ${result.group_label.toLowerCase()}${split}`;
}

/** What the figures cover: seasons, team, ground and the qualification. */
export function defaultSubtitle(result: StudioResult, options: StudioOptions): string {
  const f = result.spec.filters ?? { players: [] };
  const parts: string[] = [result.dataset_label];
  const season = (v: number | null | undefined) =>
    options.seasons.find((s) => Number(s.value) === v)?.label ?? String(v);
  if (f.season_from && f.season_to && f.season_from === f.season_to) {
    parts.push(season(f.season_from));
  } else if (f.season_from || f.season_to) {
    parts.push(
      `${f.season_from ? season(f.season_from) : "first"} to ${f.season_to ? season(f.season_to) : "latest"}`,
    );
  }
  if (f.team) parts.push(options.teams.find((t) => t.value === f.team)?.label ?? f.team);
  if (f.opponent) {
    parts.push(`v ${options.teams.find((t) => t.value === f.opponent)?.label ?? f.opponent}`);
  }
  if (f.venue) {
    parts.push(
      (options.grounds.find((g) => g.value === f.venue)?.label ?? f.venue).replace(/ \(\d+\)$/, ""),
    );
  }
  if (f.phase) parts.push(options.phases.find((p) => p.value === f.phase)?.label ?? f.phase);
  if (result.spec.min_sample) parts.push(`min ${result.spec.min_sample} ${result.sample_label}`);
  if (result.columns.some((c) => c.model)) parts.push("WPA is a model estimate");
  return parts.join(" · ");
}

/** The result as CSV columns and rows: one line per group, or per group and series. */
export function csvTable(result: StudioResult): {
  headers: string[];
  rows: (string | number | null)[][];
} {
  const measures = result.columns.map((c) => c.label);
  if (result.split_label && result.cells.length) {
    const groups = new Map(result.rows.map((r) => [r.group?.key ?? "", rowLabel(r)]));
    const series = new Map(result.series.map((r) => [r.group?.key ?? "", rowLabel(r)]));
    return {
      headers: [result.group_label ?? "", result.split_label, ...measures, result.sample_label],
      rows: result.cells.map((c) => [
        groups.get(c.group) ?? c.group,
        series.get(c.split) ?? c.split,
        ...result.columns.map((col) => c.values[col.key] ?? null),
        c.sample,
      ]),
    };
  }
  return {
    headers: [
      ...(result.spec.group_by ? ["Rank", result.group_label ?? ""] : []),
      ...measures,
      result.sample_label,
    ],
    rows: result.rows.map((r) => [
      ...(result.spec.group_by ? [r.rank, rowLabel(r)] : []),
      ...result.columns.map((col) => r.values[col.key] ?? null),
      r.sample,
    ]),
  };
}

/** Saved designs, kept in this browser only. */
export interface SavedDesign {
  name: string;
  competition: string;
  query: string;
  saved: string;
}

const STORE = "criciq:studio:designs";
const CHANGED = "criciq:studio-designs";
const MAX_SAVED = 30;

/** Saved designs from their stored text (anything malformed is dropped). */
export function parseDesigns(raw: string): SavedDesign[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (d): d is SavedDesign =>
        typeof d === "object" &&
        d !== null &&
        typeof d.name === "string" &&
        typeof d.competition === "string" &&
        typeof d.query === "string",
    );
  } catch {
    return [];
  }
}

/** The stored designs' text, for ``useSyncExternalStore`` ("[]" when storage is blocked). */
export function designsSnapshot(): string {
  try {
    return window.localStorage.getItem(STORE) ?? "[]";
  } catch {
    return "[]";
  }
}

export function subscribeDesigns(onChange: () => void): () => void {
  window.addEventListener(CHANGED, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGED, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function store(designs: SavedDesign[]): boolean {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(designs));
    window.dispatchEvent(new Event(CHANGED));
    return true;
  } catch {
    return false;
  }
}

/** Saves (or replaces, by name and competition) a design; false when the browser won't store. */
export function saveDesign(design: Omit<SavedDesign, "saved">): boolean {
  const others = parseDesigns(designsSnapshot()).filter(
    (d) => !(d.name === design.name && d.competition === design.competition),
  );
  return store([{ ...design, saved: new Date().toISOString() }, ...others].slice(0, MAX_SAVED));
}

export function deleteDesign(name: string, competition: string): void {
  store(
    parseDesigns(designsSnapshot()).filter(
      (d) => !(d.name === name && d.competition === competition),
    ),
  );
}

/** A Chart Studio path, prefilled (``parseState`` checks and completes it). */
export function studioPath(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return `/studio${text ? `?${text}` : ""}`;
}

// Record lists Chart Studio can draw: the dataset, measure and qualification (in the
// dataset's sample: balls, or matches for careers).
const RECORD_CHARTS: Record<string, { d: string; m: string; min?: number }> = {
  "most-runs": { d: "batting", m: "runs" },
  "most-hundreds": { d: "batting", m: "hundreds" },
  "most-fifties": { d: "batting", m: "fifties" },
  "most-matches": { d: "careers", m: "matches" },
  "best-batting-average": { d: "batting", m: "average", min: 500 },
  "best-batting-strike-rate": { d: "batting", m: "strike_rate", min: 500 },
  "most-fours": { d: "batting", m: "fours" },
  "most-sixes": { d: "batting", m: "sixes" },
  "most-ducks": { d: "batting", m: "ducks" },
  "highest-scores": { d: "batting", m: "highest" },
  "most-wickets": { d: "bowling", m: "wickets" },
  "best-bowling-average": { d: "bowling", m: "average", min: 600 },
  "best-bowling-strike-rate": { d: "bowling", m: "strike_rate", min: 600 },
  "best-economy": { d: "bowling", m: "economy", min: 600 },
  "most-five-wicket-innings": { d: "bowling", m: "five_wickets" },
  "most-four-wicket-innings": { d: "bowling", m: "four_wickets" },
  "best-bowling-figures": { d: "bowling", m: "best" },
  "most-catches": { d: "careers", m: "catches" },
  "most-stumpings": { d: "careers", m: "stumpings" },
};

/** The Chart Studio leaderboard for a record list, when the studio has its measure. */
export function recordChartPath(
  key: string,
  filters: { team?: string; opponent?: string; venue?: string; from?: string; to?: string } = {},
): string | null {
  const chart = RECORD_CHARTS[key];
  if (!chart) return null;
  return studioPath({
    t: "leaderboard",
    d: chart.d,
    m: chart.m,
    min: chart.min,
    team: filters.team,
    opp: filters.opponent,
    venue: filters.venue,
    from: filters.from,
    to: filters.to,
  });
}
