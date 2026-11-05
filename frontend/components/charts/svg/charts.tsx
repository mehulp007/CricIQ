/**
 * The exportable chart types. Each draws inside a ChartFrame's plot area from plain rows,
 * in the frame's units, with every value written on the chart (an image travels without
 * its tooltip).
 */

import { Legend, frameMetrics, type PlotArea } from "@/components/charts/svg/frame";
import { FONTS, type ChartTheme } from "@/components/charts/svg/theme";
import { fitText, formatFigure, linear, niceTicks } from "@/lib/chart-scale";

export interface BarRow {
  label: string;
  value: number | null;
  /** The figure as written ("75*", "3/27"); the value formatted by default. */
  display?: string;
  /** A colour of its own (a phase, a team); the theme's first series otherwise. */
  color?: string;
}

interface Base {
  plot: PlotArea;
  theme: ChartTheme;
  /** The frame's size, for type sizes. */
  frame: { width: number; height: number };
}

const shown = (row: BarRow, digits = 2) => row.display ?? formatFigure(row.value, digits);

/** Horizontal bars with their figures beside them: a leaderboard, a career by format. */
export function BarChart({ plot, theme, frame, rows }: Base & { rows: BarRow[] }) {
  const m = frameMetrics(frame.width, frame.height);
  const values = rows.map((r) => r.value ?? 0);
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values, 1e-9);
  const labelWidth = plot.width * 0.3;
  const figureWidth = plot.width * 0.14;
  const x = linear([lo, hi], [plot.x + labelWidth, plot.x + plot.width - figureWidth]);
  const slot = plot.height / Math.max(1, rows.length);
  const bar = Math.min(slot * 0.68, m.label * 2.6);
  const font = Math.min(m.label * 1.1, slot * 0.5);

  return (
    <g>
      {rows.map((row, i) => {
        const cy = plot.y + slot * i + slot / 2;
        const v = row.value ?? 0;
        const x0 = x(Math.min(0, v));
        const x1 = x(Math.max(0, v));
        return (
          <g key={`${row.label}-${i}`}>
            <text
              x={plot.x + labelWidth - font * 0.8}
              y={cy + font * 0.35}
              textAnchor="end"
              fill={theme.foreground}
              fontFamily={FONTS.body}
              fontSize={font}
            >
              {fitText(row.label, labelWidth - font, font)}
            </text>
            <rect
              x={x0}
              y={cy - bar / 2}
              width={Math.max(row.value === null ? 0 : 2, x1 - x0)}
              height={bar}
              rx={Math.min(6, bar / 4)}
              fill={row.color ?? theme.series[0]}
            />
            <text
              x={x1 + font * 0.6}
              y={cy + font * 0.35}
              fill={theme.foreground}
              fontFamily={FONTS.mono}
              fontSize={font}
              fontWeight={600}
            >
              {shown(row)}
            </text>
          </g>
        );
      })}
    </g>
  );
}

/** Vertical columns along an axis, with an optional line on its own scale (wickets per over). */
export function ColumnChart({
  plot,
  theme,
  frame,
  rows,
  line,
  labelEvery = 1,
}: Base & {
  rows: BarRow[];
  line?: { label: string; values: (number | null)[]; color?: string };
  /** Label every n-th column (overs 1, 5, 10, ...). */
  labelEvery?: number;
}) {
  const m = frameMetrics(frame.width, frame.height);
  const font = m.label;
  const axisWidth = font * 3.2;
  const bottom = plot.y + plot.height - font * 2;
  const top = plot.y + (line ? font * 2 : font * 0.5);
  const ticks = niceTicks(0, Math.max(...rows.map((r) => r.value ?? 0), 1e-9), 4);
  const y = linear([0, ticks[ticks.length - 1] || 1], [bottom, top]);
  const left = plot.x + axisWidth;
  const width = plot.width - axisWidth - (line ? axisWidth : 0);
  const slot = width / Math.max(1, rows.length);
  const lineMax = line ? Math.max(...line.values.map((v) => v ?? 0), 1e-9) : 1;
  const ly = linear([0, lineMax * 1.15], [bottom, top]);
  const lineColor = line?.color ?? theme.foreground;
  const points = line
    ? line.values
        .map((v, i) => (v === null ? null : `${left + slot * i + slot / 2},${ly(v)}`))
        .filter((p): p is string => p !== null)
    : [];

  return (
    <g>
      {line && (
        <Legend
          x={left}
          y={plot.y + font}
          theme={theme}
          fontSize={font}
          items={[{ label: line.label, color: lineColor }]}
        />
      )}
      {ticks.map((t) => (
        <g key={t}>
          <line x1={left} x2={left + width} y1={y(t)} y2={y(t)} stroke={theme.grid} />
          <text
            x={left - font * 0.5}
            y={y(t) + font * 0.35}
            textAnchor="end"
            fill={theme.muted}
            fontFamily={FONTS.mono}
            fontSize={font * 0.9}
          >
            {formatFigure(t, 1)}
          </text>
        </g>
      ))}
      {rows.map((row, i) => {
        const v = row.value ?? 0;
        const h = bottom - y(v);
        return (
          <g key={`${row.label}-${i}`}>
            <rect
              x={left + slot * i + slot * 0.14}
              y={bottom - h}
              width={slot * 0.72}
              height={Math.max(0, h)}
              rx={Math.min(4, slot * 0.15)}
              fill={row.color ?? theme.series[0]}
            >
              <title>{`${row.label}: ${shown(row)}`}</title>
            </rect>
            {(i % labelEvery === 0 || i === rows.length - 1) && (
              <text
                x={left + slot * i + slot / 2}
                y={bottom + font * 1.4}
                textAnchor="middle"
                fill={theme.muted}
                fontFamily={FONTS.mono}
                fontSize={font * 0.9}
              >
                {row.label}
              </text>
            )}
          </g>
        );
      })}
      {points.length > 1 && (
        <polyline
          points={points.join(" ")}
          fill="none"
          stroke={lineColor}
          strokeWidth={Math.max(1.5, font * 0.15)}
          strokeLinejoin="round"
        />
      )}
      {points.map((p) => {
        const [cx, cy] = p.split(",").map(Number);
        return <circle key={p} cx={cx} cy={cy} r={font * 0.22} fill={lineColor} />;
      })}
    </g>
  );
}

export interface SeriesRow {
  label: string;
  values: (number | null)[];
  /** Figures as written, matching ``values``. */
  displays?: (string | undefined)[];
}

/**
 * Several measures for each row (runs, average, strike rate by format). Each measure has
 * its own scale, since runs and averages don't share one; every bar carries its figure.
 */
export function GroupedBars({
  plot,
  theme,
  frame,
  rows,
  series,
}: Base & { rows: SeriesRow[]; series: string[] }) {
  const m = frameMetrics(frame.width, frame.height);
  const font = m.label;
  const legendHeight = font * 2;
  const labelWidth = plot.width * 0.22;
  const figureWidth = plot.width * 0.12;
  const maxes = series.map((_, s) => Math.max(...rows.map((r) => r.values[s] ?? 0), 1e-9));
  const area = plot.height - legendHeight;
  const group = area / Math.max(1, rows.length);
  const bar = Math.min((group * 0.78) / Math.max(1, series.length), font * 1.8);
  const color = (s: number) => theme.series[s % theme.series.length];
  const barFont = Math.min(font, bar * 0.8);

  return (
    <g>
      <Legend
        x={plot.x + labelWidth}
        y={plot.y + font}
        theme={theme}
        fontSize={font}
        items={series.map((label, s) => ({ label, color: color(s) }))}
      />
      {rows.map((row, i) => {
        const gy = plot.y + legendHeight + group * i + (group - bar * series.length) / 2;
        return (
          <g key={`${row.label}-${i}`}>
            <text
              x={plot.x + labelWidth - font}
              y={gy + (bar * series.length) / 2 + font * 0.35}
              textAnchor="end"
              fill={theme.foreground}
              fontFamily={FONTS.body}
              fontSize={font * 1.05}
              fontWeight={600}
            >
              {fitText(row.label, labelWidth - font * 1.5, font * 1.05)}
            </text>
            {series.map((name, s) => {
              const v = row.values[s];
              const w = v === null ? 0 : ((plot.width - labelWidth - figureWidth) * v) / maxes[s];
              const by = gy + bar * s;
              return (
                <g key={name}>
                  <rect
                    x={plot.x + labelWidth}
                    y={by + bar * 0.1}
                    width={Math.max(v === null ? 0 : 2, w)}
                    height={bar * 0.8}
                    rx={Math.min(4, bar / 4)}
                    fill={color(s)}
                  />
                  <text
                    x={plot.x + labelWidth + Math.max(0, w) + font * 0.5}
                    y={by + bar * 0.5 + barFont * 0.35}
                    fill={theme.foreground}
                    fontFamily={FONTS.mono}
                    fontSize={barFont}
                  >
                    {row.displays?.[s] ?? formatFigure(v)}
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
    </g>
  );
}

/** One or more lines over shared x labels (a career season by season). */
export function LineChart({
  plot,
  theme,
  frame,
  labels,
  series,
}: Base & { labels: string[]; series: { name: string; values: (number | null)[] }[] }) {
  const m = frameMetrics(frame.width, frame.height);
  const font = m.label;
  const axisWidth = font * 3.4;
  const top = plot.y + font * 2.4;
  const bottom = plot.y + plot.height - font * 2;
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  const ticks = niceTicks(Math.min(0, ...all), Math.max(...all, 1e-9), 4);
  const y = linear([ticks[0], ticks[ticks.length - 1] || 1], [bottom, top]);
  const left = plot.x + axisWidth;
  const width = plot.width - axisWidth - font;
  const x = linear([0, Math.max(1, labels.length - 1)], [left, left + width]);
  const every = Math.max(1, Math.ceil(labels.length / 10));
  const color = (i: number) => theme.series[i % theme.series.length];

  return (
    <g>
      <Legend
        x={left}
        y={plot.y + font}
        theme={theme}
        fontSize={font}
        items={series.map((s, i) => ({ label: s.name, color: color(i) }))}
      />
      {ticks.map((t) => (
        <g key={t}>
          <line x1={left} x2={left + width} y1={y(t)} y2={y(t)} stroke={theme.grid} />
          <text
            x={left - font * 0.5}
            y={y(t) + font * 0.35}
            textAnchor="end"
            fill={theme.muted}
            fontFamily={FONTS.mono}
            fontSize={font * 0.9}
          >
            {formatFigure(t, 1)}
          </text>
        </g>
      ))}
      {labels.map((label, i) =>
        i % every === 0 || i === labels.length - 1 ? (
          <text
            key={`${label}-${i}`}
            x={labels.length === 1 ? left + width / 2 : x(i)}
            y={bottom + font * 1.4}
            textAnchor="middle"
            fill={theme.muted}
            fontFamily={FONTS.mono}
            fontSize={font * 0.9}
          >
            {label}
          </text>
        ) : null,
      )}
      {series.map((s, si) => {
        const at = (i: number) => (labels.length === 1 ? left + width / 2 : x(i));
        const pts = s.values
          .map((v, i) => (v === null ? null : ([at(i), y(v), v] as const)))
          .filter((p): p is readonly [number, number, number] => p !== null);
        return (
          <g key={s.name}>
            {pts.length > 1 && (
              <polyline
                points={pts.map(([px, py]) => `${px},${py}`).join(" ")}
                fill="none"
                stroke={color(si)}
                strokeWidth={Math.max(2, font * 0.2)}
                strokeLinejoin="round"
              />
            )}
            {pts.map(([px, py, v], i) => (
              <circle key={i} cx={px} cy={py} r={font * 0.3} fill={color(si)}>
                <title>{`${s.name}: ${formatFigure(v)}`}</title>
              </circle>
            ))}
            {pts.length > 0 && (
              <text
                x={pts[pts.length - 1][0]}
                y={pts[pts.length - 1][1] - font * 0.8}
                textAnchor="end"
                fill={color(si)}
                fontFamily={FONTS.mono}
                fontSize={font}
                fontWeight={600}
              >
                {formatFigure(pts[pts.length - 1][2])}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}

/** A small bar chart per measure, side by side (each measure ranked on its own). */
export function SmallMultiples({
  plot,
  theme,
  frame,
  panels,
}: Base & { panels: { title: string; rows: BarRow[] }[] }) {
  const m = frameMetrics(frame.width, frame.height);
  const columns =
    frame.width >= frame.height * 1.3 ? Math.min(3, panels.length) : Math.min(2, panels.length);
  const rowsOfPanels = Math.ceil(panels.length / Math.max(1, columns));
  const gap = m.pad * 0.6;
  const pw = (plot.width - gap * (columns - 1)) / Math.max(1, columns);
  const ph = (plot.height - gap * (rowsOfPanels - 1)) / Math.max(1, rowsOfPanels);
  return (
    <g>
      {panels.map((panel, i) => {
        const px = plot.x + (i % columns) * (pw + gap);
        const py = plot.y + Math.floor(i / columns) * (ph + gap);
        const head = m.label * 1.8;
        return (
          <g key={panel.title}>
            <text
              x={px}
              y={py + m.label}
              fill={theme.muted}
              fontFamily={FONTS.body}
              fontSize={m.label}
              fontWeight={600}
            >
              {fitText(panel.title.toUpperCase(), pw, m.label)}
            </text>
            <BarChart
              plot={{ x: px, y: py + head, width: pw, height: ph - head }}
              theme={theme}
              frame={{ width: frame.width / columns, height: frame.height / rowsOfPanels }}
              rows={panel.rows}
            />
          </g>
        );
      })}
    </g>
  );
}

/** One to three big figures with their labels (a match card's headline, a career total). */
export function HeadlineNumber({
  plot,
  theme,
  frame,
  items,
}: Base & { items: { label: string; value: string; hint?: string }[] }) {
  const m = frameMetrics(frame.width, frame.height);
  const shownItems = items.slice(0, 3);
  const stacked = frame.height > frame.width;
  const cell = stacked
    ? plot.height / Math.max(1, shownItems.length)
    : plot.width / Math.max(1, shownItems.length);
  const big = Math.min(stacked ? cell * 0.45 : cell * 0.3, plot.height * 0.42, m.title * 3.2);
  return (
    <g>
      {shownItems.map((item, i) => {
        const cx = stacked ? plot.x + plot.width / 2 : plot.x + cell * i + cell / 2;
        const cy = stacked ? plot.y + cell * i + cell / 2 : plot.y + plot.height / 2;
        return (
          <g key={`${item.label}-${i}`}>
            <text
              x={cx}
              y={cy}
              textAnchor="middle"
              fill={i === 0 ? theme.series[0] : theme.foreground}
              fontFamily={FONTS.mono}
              fontSize={big}
              fontWeight={700}
            >
              {item.value}
            </text>
            <text
              x={cx}
              y={cy + m.label * 2.2}
              textAnchor="middle"
              fill={theme.muted}
              fontFamily={FONTS.body}
              fontSize={m.label * 1.2}
            >
              {fitText(
                item.label.toUpperCase(),
                (stacked ? plot.width : cell) * 0.9,
                m.label * 1.2,
              )}
            </text>
            {item.hint && (
              <text
                x={cx}
                y={cy + m.label * 4}
                textAnchor="middle"
                fill={theme.muted}
                fontFamily={FONTS.body}
                fontSize={m.label}
              >
                {fitText(item.hint, (stacked ? plot.width : cell) * 0.9, m.label)}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}

/** A table drawn as an image: the figures behind a note, a scorecard summary. */
export function TableCard({
  plot,
  theme,
  frame,
  columns,
  rows,
}: Base & {
  columns: { header: string; numeric?: boolean }[];
  rows: string[][];
}) {
  const m = frameMetrics(frame.width, frame.height);
  const lines = rows.length + 1;
  const rowHeight = Math.min(plot.height / Math.max(1, lines), m.label * 3);
  const font = Math.min(m.label * 1.15, rowHeight * 0.45);
  const first = plot.width * (columns.length > 4 ? 0.28 : 0.36);
  const rest = (plot.width - first) / Math.max(1, columns.length - 1);
  // Figures align to the right edge of their column.
  const colX = (c: number) => plot.x + first + rest * c - font * 0.4;
  return (
    <g>
      {[columns.map((c) => c.header), ...rows].map((cells, r) => {
        const ry = plot.y + rowHeight * r;
        return (
          <g key={r}>
            {r > 0 && r % 2 === 0 && (
              <rect
                x={plot.x}
                y={ry}
                width={plot.width}
                height={rowHeight}
                fill={theme.grid}
                opacity={0.35}
              />
            )}
            {cells.map((cell, c) => {
              const numeric = columns[c]?.numeric ?? c > 0;
              return (
                <text
                  key={c}
                  x={c === 0 ? plot.x + font * 0.4 : colX(c)}
                  y={ry + rowHeight / 2 + font * 0.35}
                  textAnchor={numeric && c > 0 ? "end" : "start"}
                  fill={r === 0 ? theme.muted : theme.foreground}
                  fontFamily={numeric && r > 0 ? FONTS.mono : FONTS.body}
                  fontSize={r === 0 ? font * 0.85 : font}
                  fontWeight={r === 0 || c === 0 ? 600 : 400}
                >
                  {fitText(
                    r === 0 ? cell.toUpperCase() : cell,
                    c === 0 ? first - font : rest * 0.9,
                    font,
                  )}
                </text>
              );
            })}
          </g>
        );
      })}
    </g>
  );
}
