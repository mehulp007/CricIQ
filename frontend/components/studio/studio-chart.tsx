"use client";

import type { Ref } from "react";

import {
  BarChart,
  ColumnChart,
  GroupedBars,
  HeadlineNumber,
  LineChart,
  SmallMultiples,
  TableCard,
  type BarRow,
} from "@/components/charts/svg/charts";
import { ChartFrame, type PlotArea } from "@/components/charts/svg/frame";
import { CHART_SIZES, chartTheme, type ChartTheme } from "@/components/charts/svg/theme";
import type { InningsScorecard, MatchDetail, StudioResult } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { resolveChart, rowLabel, type StudioStyle } from "@/lib/studio";

// Rows an image can hold legibly, by its shape.
const TABLE_ROWS = { landscape: 12, square: 18, portrait: 30 } as const;
const PANEL_ROWS = 8;

interface Frame {
  theme: ChartTheme;
  frame: { width: number; height: number };
}

/** A Chart Studio result drawn as the chosen chart, inside an exportable frame. */
export function StudioChart({
  result,
  style,
  title,
  subtitle,
  footer,
  image,
  svgRef,
}: {
  result: StudioResult;
  style: StudioStyle;
  title: string;
  subtitle: string;
  footer: string;
  image: string | null;
  svgRef: Ref<SVGSVGElement>;
}) {
  const size = CHART_SIZES[style.size];
  const theme = chartTheme(style.theme, style.accent);
  const kind = resolveChart(result, style.chart);
  return (
    <ChartFrame
      width={size.width}
      height={size.height}
      theme={theme}
      title={title}
      subtitle={subtitle}
      footer={footer}
      image={image}
      svgRef={svgRef}
      description={`${title}: ${kind} chart of ${result.columns.map((c) => c.label).join(", ")}. The figures are in the Table tab.`}
    >
      {(plot) => (
        <Plot
          result={result}
          kind={kind}
          plot={plot}
          theme={theme}
          frame={size}
          labels={style.labels}
          size={style.size}
        />
      )}
    </ChartFrame>
  );
}

function Plot({
  result,
  kind,
  plot,
  theme,
  frame,
  labels,
  size,
}: Frame & {
  result: StudioResult;
  kind: ReturnType<typeof resolveChart>;
  plot: PlotArea;
  labels: boolean;
  size: StudioStyle["size"];
}) {
  const base = { plot, theme, frame };
  const columns = result.columns;
  const first = columns[0];
  const split = Boolean(result.split_label);
  const bars = (key: string, rows = result.rows): BarRow[] =>
    rows.map((r) => ({
      label: rowLabel(r),
      value: r.values[key] ?? null,
      display: r.display[key],
      color: r.group?.color ?? undefined,
    }));
  const cell = (group: string, series: string) =>
    result.cells.find((c) => c.group === group && c.split === series);

  if (kind === "headline") {
    const row = result.rows[0];
    if (!row) return null;
    return (
      <HeadlineNumber
        {...base}
        items={columns.slice(0, 3).map((c) => ({
          label: c.label,
          value: row.display[c.key] ?? "—",
        }))}
      />
    );
  }
  if (kind === "bars") {
    return <BarChart {...base} rows={bars(first.key)} labels={labels} />;
  }
  if (kind === "columns") {
    return (
      <ColumnChart
        {...base}
        rows={bars(first.key)}
        values={labels}
        labelEvery={result.rows.length > 25 ? 5 : 1}
      />
    );
  }
  if (kind === "line") {
    const groups = result.rows;
    const series = split
      ? result.series.map((s) => ({
          name: rowLabel(s),
          values: groups.map((g) => {
            const found = cell(g.group?.key ?? "", s.group?.key ?? "");
            return found ? (found.values[first.key] ?? null) : null;
          }),
        }))
      : [{ name: first.label, values: groups.map((g) => g.values[first.key] ?? null) }];
    return <LineChart {...base} labels={groups.map(rowLabel)} series={series} values={labels} />;
  }
  if (kind === "grouped") {
    if (split) {
      return (
        <GroupedBars
          {...base}
          labels={labels}
          sharedScale
          series={result.series.map(rowLabel)}
          rows={result.rows.map((g) => {
            const found = result.series.map((s) => cell(g.group?.key ?? "", s.group?.key ?? ""));
            return {
              label: rowLabel(g),
              values: found.map((c) => c?.values[first.key] ?? null),
              displays: found.map((c) => c?.display[first.key]),
            };
          })}
        />
      );
    }
    return (
      <GroupedBars
        {...base}
        labels={labels}
        series={columns.map((c) => c.label)}
        rows={result.rows.map((r) => ({
          label: rowLabel(r),
          values: columns.map((c) => r.values[c.key] ?? null),
          displays: columns.map((c) => r.display[c.key]),
        }))}
      />
    );
  }
  if (kind === "multiples") {
    return (
      <SmallMultiples
        {...base}
        labels={labels}
        panels={columns.map((c) => {
          const ranked = [...result.rows]
            .filter((r) => r.values[c.key] !== null && r.values[c.key] !== undefined)
            .sort((a, b) => {
              const d = (a.values[c.key] ?? 0) - (b.values[c.key] ?? 0);
              return c.descending ? -d : d;
            })
            .slice(0, PANEL_ROWS);
          return { title: c.label, rows: bars(c.key, ranked) };
        })}
      />
    );
  }
  const rows = result.rows.slice(0, TABLE_ROWS[size]);
  return (
    <TableCard
      {...base}
      columns={[
        { header: result.group_label ?? "" },
        ...columns.map((c) => ({ header: c.label, numeric: true })),
      ]}
      rows={rows.map((r) => [
        r.rank === null || r.rank === undefined
          ? rowLabel(r)
          : `${r.tied ? "=" : ""}${r.rank}  ${rowLabel(r)}`,
        ...columns.map((c) => r.display[c.key] ?? "—"),
      ])}
    />
  );
}

function topBatter(innings: InningsScorecard): string {
  const best = [...innings.batting].sort((a, b) => b.runs - a.runs || a.balls - b.balls)[0];
  return best ? `${best.name} ${best.runs}${best.is_out ? "" : "*"} (${best.balls})` : "—";
}

function topBowler(innings: InningsScorecard): string {
  const best = [...innings.bowling].sort((a, b) => b.wickets - a.wickets || a.runs - b.runs)[0];
  return best ? `${best.name} ${best.wickets}/${best.runs}` : "—";
}

export function matchTitle(match: MatchDetail): string {
  return `${match.summary.team_a.name} v ${match.summary.team_b.name}`;
}

export function matchSubtitle(match: MatchDetail): string {
  const s = match.summary;
  const pom = s.player_of_match.length
    ? `Player of the match: ${s.player_of_match.join(", ")}`
    : "";
  return [s.result_text, s.venue.name, formatDate(s.date), pom].filter(Boolean).join(" · ");
}

/** The match card's table: each innings' total and its best batter and bowler. */
export function matchRows(match: MatchDetail): string[][] {
  return match.innings
    .filter((i) => !i.is_super_over)
    .map((i) => [
      i.batting_team.name,
      `${i.runs}/${i.wickets} (${i.overs})`,
      topBatter(i),
      topBowler(i),
    ]);
}

/** A match's scorecard as an exportable card. */
export function MatchCard({
  match,
  style,
  title,
  subtitle,
  footer,
  image,
  svgRef,
}: {
  match: MatchDetail;
  style: StudioStyle;
  title: string;
  subtitle: string;
  footer: string;
  image: string | null;
  svgRef: Ref<SVGSVGElement>;
}) {
  const size = CHART_SIZES[style.size];
  const theme = chartTheme(style.theme, style.accent);
  return (
    <ChartFrame
      width={size.width}
      height={size.height}
      theme={theme}
      title={title}
      subtitle={subtitle}
      footer={footer}
      image={image}
      svgRef={svgRef}
      description={`${title}: each innings' total with its top batter and bowler.`}
    >
      {(plot) => (
        <TableCard
          plot={plot}
          theme={theme}
          frame={size}
          columns={[
            { header: "Innings" },
            { header: "Score", numeric: true },
            { header: "Top batter", numeric: false },
            { header: "Top bowler", numeric: false },
          ]}
          rows={matchRows(match)}
        />
      )}
    </ChartFrame>
  );
}
