import type { ReactNode, Ref } from "react";
import { useId } from "react";

import { FONTS, type ChartTheme } from "@/components/charts/svg/theme";
import { fitText } from "@/lib/chart-scale";

/** Where a chart draws inside its frame, in the frame's own units. */
export interface PlotArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Type sizes for a frame, from its width (an image keeps its proportions at any size). */
export function frameMetrics(width: number, height: number) {
  const base = Math.min(width, height * 1.6);
  const pad = Math.round(base * 0.045);
  const title = Math.round(base * 0.034);
  const subtitle = Math.round(base * 0.018);
  const footer = Math.round(base * 0.0135);
  const label = Math.max(11, Math.round(base * 0.015));
  return { pad, title, subtitle, footer, label };
}

/**
 * The frame every exportable chart draws in: a background, the title and subtitle, the
 * plot and a footer naming the data. It is one self-contained ``<svg>`` (no CSS from the
 * page beyond variables, which the exporter resolves), so the same element shows on the
 * page and becomes the PNG or SVG file.
 */
export function ChartFrame({
  width,
  height,
  theme,
  title,
  subtitle,
  footer,
  description,
  svgRef,
  className,
  children,
}: {
  width: number;
  height: number;
  theme: ChartTheme;
  title: string;
  subtitle?: string;
  /** The data line: source, data version or date checked. */
  footer: string;
  /** What the chart shows, for screen readers (the figures are in the page's table). */
  description: string;
  svgRef?: Ref<SVGSVGElement>;
  className?: string;
  children: (plot: PlotArea) => ReactNode;
}) {
  const id = useId();
  const m = frameMetrics(width, height);
  const inner = width - m.pad * 2;
  const titleY = m.pad + m.title;
  const subtitleY = titleY + (subtitle ? m.subtitle * 1.7 : 0);
  const top = subtitleY + m.pad * 0.8;
  const footerY = height - m.pad;
  const plot: PlotArea = {
    x: m.pad,
    y: top,
    width: inner,
    height: Math.max(10, footerY - m.footer * 2.2 - top),
  };

  return (
    <svg
      ref={svgRef}
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-labelledby={`${id}-title ${id}-desc`}
      className={className}
      style={{ height: "auto", maxWidth: "100%" }}
      data-export-width={width}
      data-export-height={height}
    >
      <title id={`${id}-title`}>{title}</title>
      <desc id={`${id}-desc`}>{description}</desc>
      <rect width={width} height={height} rx={Math.round(m.pad * 0.5)} fill={theme.background} />
      <text
        x={m.pad}
        y={titleY}
        fill={theme.foreground}
        fontFamily={FONTS.heading}
        fontSize={m.title}
        fontWeight={700}
      >
        {fitText(title, inner, m.title)}
      </text>
      {subtitle && (
        <text
          x={m.pad}
          y={subtitleY}
          fill={theme.muted}
          fontFamily={FONTS.body}
          fontSize={m.subtitle}
        >
          {fitText(subtitle, inner, m.subtitle)}
        </text>
      )}
      {children(plot)}
      <line
        x1={m.pad}
        x2={width - m.pad}
        y1={footerY - m.footer * 1.5}
        y2={footerY - m.footer * 1.5}
        stroke={theme.grid}
      />
      <text
        x={m.pad}
        y={footerY}
        fill={theme.foreground}
        fontFamily={FONTS.heading}
        fontSize={m.footer}
        fontWeight={700}
      >
        CricIQ
      </text>
      <text
        x={width - m.pad}
        y={footerY}
        textAnchor="end"
        fill={theme.muted}
        fontFamily={FONTS.body}
        fontSize={m.footer}
      >
        {fitText(footer, inner * 0.8, m.footer)}
      </text>
    </svg>
  );
}

/** A row of coloured keys above a plot. */
export function Legend({
  x,
  y,
  items,
  theme,
  fontSize,
}: {
  x: number;
  y: number;
  items: { label: string; color: string }[];
  theme: ChartTheme;
  fontSize: number;
}) {
  // Each key starts where the one before it (swatch, label and a gap) ends.
  const widths = items.map((item) => fontSize * 3 + item.label.length * fontSize * 0.56);
  const placed = items.map((item, i) => ({
    ...item,
    at: widths.slice(0, i).reduce((sum, w) => sum + w, 0),
  }));
  return (
    <g>
      {placed.map((item) => (
        <g key={item.label} transform={`translate(${x + item.at} ${y})`}>
          <rect y={-fontSize * 0.8} width={fontSize} height={fontSize} rx={2} fill={item.color} />
          <text x={fontSize * 1.5} fill={theme.muted} fontFamily={FONTS.body} fontSize={fontSize}>
            {item.label}
          </text>
        </g>
      ))}
    </g>
  );
}
