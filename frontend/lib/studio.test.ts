import { afterEach, describe, expect, it } from "vitest";

import type { StudioOptions, StudioResult } from "@/lib/api/types";
import { fileName } from "@/lib/export-image";
import {
  csvTable,
  defaultSubtitle,
  defaultTitle,
  deleteDesign,
  designsSnapshot,
  normalizeSpec,
  parseDesigns,
  parseState,
  recordChartPath,
  resolveChart,
  saveDesign,
  stateToParams,
  studioPath,
  templateState,
  TEMPLATES,
  type StudioState,
} from "@/lib/studio";

const coverage = {
  first_season: 2008,
  last_season: 2024,
  first_season_label: "2008",
  last_season_label: "2024",
  matches: 1100,
  first_date: "2008-04-18",
  last_date: "2024-05-26",
};

const column = (key: string, label: string, kind = "count", descending = true) => ({
  key,
  label,
  kind: kind as "count",
  description: label,
  model: key === "wpa",
  descending,
});

const dims = (...keys: string[]) =>
  keys.map((key) => ({
    key: key as "player",
    label: key,
    natural: ["season", "position", "phase", "innings"].includes(key),
  }));

export const OPTIONS: StudioOptions = {
  coverage,
  data_version: "2024-06-01.abc",
  format: "T20",
  max_series: 8,
  datasets: [
    {
      key: "batting",
      label: "Batting innings",
      description: "",
      sample_label: "balls faced",
      measures: [
        column("runs", "Runs"),
        column("average", "Average", "rate"),
        column("strike_rate", "Strike rate", "rate"),
        column("boundary_pct", "Boundary %", "pct"),
        column("sixes", "6s"),
        column("wpa", "Win probability added", "wpa"),
      ],
      dimensions: dims("player", "team", "season", "opponent", "ground", "position", "innings"),
      filters: ["innings", "opponent", "players", "position", "season", "team", "venue"],
      default_measures: ["runs", "average", "strike_rate"],
      needs_player: false,
    },
    {
      key: "bowling",
      label: "Bowling innings",
      description: "",
      sample_label: "balls bowled",
      measures: [
        column("wickets", "Wickets"),
        column("economy", "Economy", "rate", false),
        column("average", "Bowling average", "rate", false),
        column("dot_pct", "Dot %", "pct"),
      ],
      dimensions: dims("player", "team", "season", "opponent", "ground", "innings"),
      filters: ["innings", "opponent", "players", "season", "team", "venue"],
      default_measures: ["wickets", "economy", "average"],
      needs_player: false,
    },
    {
      key: "careers",
      label: "Careers",
      description: "",
      sample_label: "matches",
      measures: [
        column("matches", "Matches"),
        column("runs", "Runs"),
        column("wickets", "Wickets"),
      ],
      dimensions: dims("player", "team", "season", "opponent", "ground"),
      filters: ["opponent", "players", "season", "team", "venue"],
      default_measures: ["matches", "runs", "wickets"],
      needs_player: true,
    },
    {
      key: "teams",
      label: "Team results",
      description: "",
      sample_label: "matches",
      measures: [column("matches", "Matches"), column("won", "Won"), column("win_pct", "Win %")],
      dimensions: dims("team", "season", "opponent", "ground", "innings"),
      filters: ["innings", "opponent", "season", "team", "venue"],
      default_measures: ["matches", "won", "win_pct"],
      needs_player: false,
    },
  ],
  teams: [
    { value: "MI", label: "Mumbai Indians", color: "#004ba0" },
    { value: "CSK", label: "Chennai Super Kings", color: "#f9cd05" },
  ],
  grounds: [{ value: "wankhede", label: "Wankhede Stadium (110)", color: null }],
  seasons: [
    { value: "2023", label: "2023", color: null },
    { value: "2024", label: "2024", color: null },
  ],
  phases: [
    { value: "powerplay", label: "Powerplay", color: null },
    { value: "middle", label: "Middle overs", color: null },
    { value: "death", label: "Death overs", color: null },
  ],
};

function result(part: Partial<StudioResult> = {}): StudioResult {
  return {
    coverage,
    data_version: "2024-06-01.abc",
    format: "T20",
    spec: normalizeSpec({ dataset: "batting", measures: ["runs"] }, OPTIONS),
    dataset_label: "Batting innings",
    group_label: "Player",
    split_label: null,
    sample_label: "balls faced",
    columns: [column("runs", "Runs")],
    rows: [
      {
        group: { key: "kohli", label: "Virat Kohli", player_id: "kohli", color: null },
        rank: 1,
        tied: false,
        values: { runs: 8004 },
        display: { runs: "8,004" },
        sample: 6200,
      },
      {
        group: { key: "rohit", label: "Rohit Sharma", player_id: "rohit", color: null },
        rank: 2,
        tied: false,
        values: { runs: 6628 },
        display: { runs: "6,628" },
        sample: 5100,
      },
    ],
    series: [],
    cells: [],
    truncated: false,
    sql: "SELECT ...",
    params: [],
    ...part,
  };
}

describe("normalizeSpec", () => {
  it("drops measures, groupings and filters the dataset doesn't have", () => {
    const spec = normalizeSpec(
      {
        dataset: "bowling",
        measures: ["runs", "wickets", "wickets", "economy"],
        group_by: "position",
        split_by: "position",
        filters: { players: ["a'b", "bumrah"], position: 3, team: "XX", phase: "death" },
        sort: "average",
        limit: 500,
      },
      OPTIONS,
    );
    expect(spec.measures).toEqual(["wickets", "economy"]);
    expect(spec.group_by).toBe("player");
    expect(spec.split_by).toBeNull();
    expect(spec.filters).toMatchObject({ players: ["bumrah"], position: null, team: null });
    expect(spec.filters?.phase).toBeNull();
    expect(spec.sort).toBeNull();
    expect(spec.limit).toBe(50);
  });

  it("falls back to the dataset's defaults and keeps careers grouped by player", () => {
    expect(normalizeSpec({ dataset: "batting", measures: [] }, OPTIONS).measures).toEqual([
      "runs",
      "average",
      "strike_rate",
    ]);
    const careers = normalizeSpec(
      { dataset: "careers", measures: ["runs"], group_by: "season" },
      OPTIONS,
    );
    expect([careers.group_by, careers.split_by]).toEqual(["season", "player"]);
    expect(
      normalizeSpec({ dataset: "careers", measures: ["runs"], group_by: null }, OPTIONS).group_by,
    ).toBe("player");
  });

  it("orders a season range and only sorts by the grouping when it has an order", () => {
    const spec = normalizeSpec(
      {
        dataset: "batting",
        measures: ["runs"],
        filters: { players: [], season_from: 2024, season_to: 2023 },
      },
      OPTIONS,
    );
    expect([spec.filters?.season_from, spec.filters?.season_to]).toEqual([2023, 2024]);
    expect(
      normalizeSpec({ dataset: "batting", measures: ["runs"], sort: "group" }, OPTIONS).sort,
    ).toBeNull();
    expect(
      normalizeSpec(
        { dataset: "batting", measures: ["runs"], group_by: "season", sort: "group" },
        OPTIONS,
      ).sort,
    ).toBe("group");
  });
});

describe("the URL", () => {
  it("round-trips every template", () => {
    for (const t of TEMPLATES) {
      const state = templateState(t.key, OPTIONS);
      const params = stateToParams(state, OPTIONS);
      expect(parseState(params, OPTIONS)).toEqual(state);
    }
  });

  it("round-trips an edited design and writes only what differs", () => {
    const base = templateState("timeline", OPTIONS);
    const state: StudioState = {
      ...base,
      spec: normalizeSpec(
        {
          ...base.spec,
          measures: ["runs", "strike_rate"],
          filters: {
            players: ["kohli", "rohit"],
            team: "MI",
            season_from: 2023,
            venue: "wankhede",
          },
          min_sample: 120,
          series: 2,
          order: "desc",
        },
        OPTIONS,
      ),
      style: {
        chart: "grouped",
        size: "portrait",
        theme: "paper",
        accent: "#ff6600",
        title: "Kohli & Rohit",
        subtitle: "Since 2023",
        labels: false,
      },
    };
    const params = stateToParams(state, OPTIONS);
    expect(params.get("t")).toBe("timeline");
    expect(params.has("d")).toBe(false); // the template's own dataset
    expect(params.get("p")).toBe("kohli,rohit");
    expect(params.get("accent")).toBe("ff6600");
    expect(parseState(new URLSearchParams(params.toString()), OPTIONS)).toEqual(state);
    expect(stateToParams(templateState("blank", OPTIONS), OPTIONS).toString()).toBe("");
  });

  it("clears a template's season and keeps a split removed", () => {
    const season = templateState("season", OPTIONS);
    expect(season.spec.filters?.season_from).toBe(2024);
    const cleared = {
      ...season,
      spec: {
        ...season.spec,
        filters: { ...season.spec.filters, season_from: null, season_to: null },
      },
    };
    expect(
      parseState(stateToParams(cleared, OPTIONS), OPTIONS).spec.filters?.season_from,
    ).toBeNull();
    const timeline = templateState("timeline", OPTIONS);
    const flat = { ...timeline, spec: { ...timeline.spec, split_by: null } };
    expect(parseState(stateToParams(flat, OPTIONS), OPTIONS).spec.split_by).toBeNull();
  });

  it("falls back to defaults for anything a link gets wrong", () => {
    const state = parseState(
      new URLSearchParams(
        "t=nope&d=matches&m=sql,runs&g=sideways&n=-4&min=abc&chart=pie&size=huge&theme=neon&accent=red&labels=maybe&title=" +
          "x".repeat(300),
      ),
      OPTIONS,
    );
    expect(state.template).toBe("blank");
    expect(state.spec).toMatchObject({
      dataset: "batting",
      measures: ["runs"],
      group_by: "player",
    });
    expect(state.spec.limit).toBe(15);
    expect(state.style).toMatchObject({
      chart: "auto",
      size: "landscape",
      theme: "dark",
      accent: null,
    });
    expect(state.style.labels).toBe(true);
    expect(state.style.title).toHaveLength(120);
    expect(state.match).toBeNull();
    expect(parseState(new URLSearchParams("t=match&match=123"), OPTIONS).match).toBe(123);
  });
});

describe("links into the studio", () => {
  it("prefills a template", () => {
    expect(studioPath({ t: "profile", p: "kohli" })).toBe("/studio?t=profile&p=kohli");
    expect(studioPath({})).toBe("/studio");
  });

  it("draws the record lists it has a measure for", () => {
    const path = recordChartPath("best-economy", { team: "MI", from: "2023" });
    expect(path).toBe("/studio?t=leaderboard&d=bowling&m=economy&min=600&team=MI&from=2023");
    const state = parseState(new URLSearchParams(path!.split("?")[1]), OPTIONS);
    expect(state.spec).toMatchObject({
      dataset: "bowling",
      measures: ["economy"],
      min_sample: 600,
    });
    expect(state.spec.filters?.team).toBe("MI");
    expect(recordChartPath("highest-partnerships")).toBeNull();
  });
});

describe("charts and titles", () => {
  it("picks a chart that suits the result", () => {
    expect(resolveChart(result(), "auto")).toBe("bars");
    expect(resolveChart(result(), "table")).toBe("table");
    const one = result({ rows: result().rows.slice(0, 1) });
    expect(resolveChart(one, "auto")).toBe("headline");
    const seasons = result({
      spec: normalizeSpec({ dataset: "batting", measures: ["runs"], group_by: "season" }, OPTIONS),
    });
    expect(resolveChart(seasons, "auto")).toBe("line");
    const many = result({
      columns: ["runs", "average", "strike_rate", "sixes"].map((k) => column(k, k)),
    });
    expect(resolveChart(many, "auto")).toBe("table");
    const split = result({
      spec: normalizeSpec(
        { dataset: "batting", measures: ["runs"], group_by: "team", split_by: "season" },
        OPTIONS,
      ),
      split_label: "Season",
    });
    expect(resolveChart(split, "auto")).toBe("grouped");
  });

  it("writes titles from the figures", () => {
    expect(defaultTitle(result(), "IPL")).toBe("IPL: runs by player");
    expect(defaultTitle(result({ rows: result().rows.slice(0, 1) }), "IPL")).toBe(
      "Virat Kohli in the IPL",
    );
    const filtered = result({
      spec: normalizeSpec(
        {
          dataset: "batting",
          measures: ["runs"],
          filters: { players: [], season_from: 2024, season_to: 2024, team: "MI" },
          min_sample: 100,
        },
        OPTIONS,
      ),
      columns: [column("wpa", "Win probability added", "wpa")],
    });
    expect(defaultSubtitle(filtered, OPTIONS)).toBe(
      "Batting innings · 2024 · Mumbai Indians · min 100 balls faced · WPA is a model estimate",
    );
  });

  it("makes CSV rows, with a line per series cell when split", () => {
    expect(csvTable(result())).toEqual({
      headers: ["Rank", "Player", "Runs", "balls faced"],
      rows: [
        [1, "Virat Kohli", 8004, 6200],
        [2, "Rohit Sharma", 6628, 5100],
      ],
    });
    const split = result({
      split_label: "Season",
      series: [
        {
          group: { key: "2024", label: "2024", color: null, player_id: null },
          rank: null,
          tied: false,
          values: {},
          display: {},
          sample: 1,
        },
      ],
      cells: [
        {
          group: "kohli",
          split: "2024",
          values: { runs: 741 },
          display: { runs: "741" },
          sample: 480,
        },
      ],
    });
    expect(csvTable(split)).toEqual({
      headers: ["Player", "Season", "Runs", "balls faced"],
      rows: [["Virat Kohli", "2024", 741, 480]],
    });
    expect(fileName(defaultTitle(result(), "IPL"), "csv")).toBe("ipl-runs-by-player.csv");
  });
});

describe("saved designs", () => {
  afterEach(() => window.localStorage.clear());

  it("saves, replaces and deletes by name and competition", () => {
    expect(saveDesign({ name: "Kohli", competition: "ipl", query: "t=profile&p=kohli" })).toBe(
      true,
    );
    expect(
      saveDesign({ name: "Kohli", competition: "ipl", query: "t=profile&p=kohli&theme=navy" }),
    ).toBe(true);
    saveDesign({ name: "Kohli", competition: "t20i", query: "t=profile" });
    const saved = parseDesigns(designsSnapshot());
    expect(saved.map((d) => [d.name, d.competition, d.query])).toEqual([
      ["Kohli", "t20i", "t=profile"],
      ["Kohli", "ipl", "t=profile&p=kohli&theme=navy"],
    ]);
    deleteDesign("Kohli", "ipl");
    expect(parseDesigns(designsSnapshot())).toHaveLength(1);
  });

  it("ignores anything malformed", () => {
    expect(parseDesigns("not json")).toEqual([]);
    expect(parseDesigns('{"name":"x"}')).toEqual([]);
    expect(parseDesigns('[{"name":1},{"name":"a","competition":"ipl","query":""}]')).toHaveLength(
      1,
    );
  });
});
