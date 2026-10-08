"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DRAW_COLOR } from "@/components/replay/test/outcome-bar";
import { SIDE_COLORS } from "@/components/replay/win-probability-bar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ChaseCalculation, ChaseSide } from "@/lib/api/types";
import type { CompetitionId } from "@/lib/competitions";
import { formatPercent } from "@/lib/replay/win-probability";
import { cn } from "@/lib/utils";
import { fetchAwake, wakeSimulator } from "@/lib/wake";

type Venue = "home" | "away" | "neutral";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

function Slider({
  id,
  label,
  value,
  min,
  max,
  step,
  onChange,
  unit,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  unit: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="flex items-baseline justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono font-semibold tabular-nums">
          {value} <span className="text-xs font-normal text-muted-foreground">{unit}</span>
        </span>
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 cursor-pointer accent-primary"
      />
    </div>
  );
}

function SidePicker({
  label,
  value,
  sides,
  exclude,
  onChange,
}: {
  label: string;
  value: string;
  sides: ChaseSide[];
  exclude: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-full" aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {sides
            .filter((s) => s.franchise_id !== exclude)
            .map((s) => (
              <SelectItem key={s.franchise_id} value={s.franchise_id}>
                {s.name}
                {s.rating !== null && (
                  <span className="ml-2 font-mono text-xs text-muted-foreground">
                    {Math.round(s.rating)}
                  </span>
                )}
              </SelectItem>
            ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** A fourth-innings chase set up from scratch, answered by the Test win probability model. */
export function ChaseCalculator({
  competition,
  sides,
  initialBatting,
  initialFielding,
}: {
  competition: CompetitionId;
  sides: ChaseSide[];
  initialBatting: string;
  initialFielding: string;
}) {
  const [batting, setBatting] = useState(initialBatting);
  const [fielding, setFielding] = useState(initialFielding);
  const [venue, setVenue] = useState<Venue>("away");
  const [needed, setNeeded] = useState(280);
  const [wickets, setWickets] = useState(10);
  const [overs, setOvers] = useState(100);
  const [result, setResult] = useState<ChaseCalculation | null>(null);
  const [status, setStatus] = useState<"loading" | "waking" | "ready" | "error">("loading");

  useEffect(() => wakeSimulator(), []);
  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({
      batting,
      fielding,
      venue,
      needed: String(needed),
      wickets: String(wickets),
      overs: String(overs),
    });
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetchAwake(
          `/api/${competition}/chase-calculator?${params}`,
          undefined,
          () => setStatus("waking"),
        );
        if (!response.ok) throw new Error(String(response.status));
        const found = (await response.json()) as ChaseCalculation;
        if (!cancelled) {
          setResult(found);
          setStatus("ready");
        }
      } catch {
        if (!cancelled) setStatus("error");
      }
    }, 120);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [competition, batting, fielding, venue, needed, wickets, overs]);

  const name = (id: string) => sides.find((s) => s.franchise_id === id)?.name ?? id;
  const outcome = result?.outcome ?? null;
  const curve = (result?.by_runs_needed ?? []).map((o) => ({
    needed: o.runs_needed,
    won: o.won * 100,
    drawn: o.drawn * 100,
    lost: o.lost * 100,
  }));
  const venues: [Venue, string][] = [
    ["home", `In ${name(batting)}`],
    ["away", `In ${name(fielding)}`],
    ["neutral", "Neutral ground"],
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-12">
      <section
        aria-label="The chase"
        className="flex flex-col gap-5 rounded-2xl border border-border bg-card/70 p-5 lg:col-span-5"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <SidePicker
            label="Chasing"
            value={batting}
            sides={sides}
            exclude={fielding}
            onChange={setBatting}
          />
          <SidePicker
            label="Bowling"
            value={fielding}
            sides={sides}
            exclude={batting}
            onChange={setFielding}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm text-muted-foreground">Where</span>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Where the Test is played">
            {venues.map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={venue === key}
                onClick={() => setVenue(key)}
                className={cn(
                  "rounded-md border border-border px-3 py-1.5 text-xs transition-colors",
                  venue === key
                    ? "bg-secondary text-secondary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <Slider
          id="chase-needed"
          label="Runs needed"
          value={needed}
          min={10}
          max={600}
          step={10}
          unit="runs"
          onChange={setNeeded}
        />
        <Slider
          id="chase-wickets"
          label="Wickets in hand"
          value={wickets}
          min={1}
          max={10}
          step={1}
          unit="wickets"
          onChange={setWickets}
        />
        <Slider
          id="chase-overs"
          label="Overs left in the match"
          value={overs}
          min={0}
          max={200}
          step={5}
          unit="overs"
          onChange={setOvers}
        />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Overs left are counted the model&apos;s way: five days of 90 overs less those bowled, so a
          full last day is 90. Time lost to rain or bad light is not taken off.
        </p>
      </section>

      <section
        aria-label="The chances"
        aria-live="polite"
        className="flex flex-col gap-5 rounded-2xl border border-border bg-card/70 p-5 lg:col-span-7"
      >
        {outcome === null ? (
          <p className="text-sm text-muted-foreground">
            {status === "error"
              ? "The calculator is unavailable right now. Try again in a moment."
              : status === "waking"
                ? "Waking the server. The free server sleeps when nobody is using it, so this can take up to a minute…"
                : "Working out the chances…"}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3">
              {(
                [
                  [`${name(batting)} win`, outcome.won, SIDE_COLORS.a],
                  ["Draw", outcome.drawn, DRAW_COLOR],
                  [`${name(fielding)} win`, outcome.lost, SIDE_COLORS.b],
                ] as const
              ).map(([label, value, color]) => (
                <div key={label} className="flex flex-col gap-1">
                  <span className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span
                      aria-hidden="true"
                      className="size-2 rounded-full"
                      style={{ background: color }}
                    />
                    {label}
                  </span>
                  <span className="font-mono text-3xl font-semibold tracking-tight tabular-nums">
                    {formatPercent(value)}
                  </span>
                </div>
              ))}
            </div>
            <div>
              <h2 className="text-xs tracking-wide text-muted-foreground uppercase">
                The same chase for other targets
              </h2>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={curve} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                    <CartesianGrid stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="needed" type="number" domain={[10, 600]} {...AXIS} />
                    <YAxis
                      domain={[0, 100]}
                      ticks={[0, 25, 50, 75, 100]}
                      tickFormatter={(v: number) => `${v}%`}
                      width={48}
                      {...AXIS}
                    />
                    <ReferenceLine x={needed} stroke="var(--foreground)" strokeDasharray="4 3" />
                    <Tooltip
                      contentStyle={{
                        background: "var(--popover)",
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelFormatter={(v) => `${v} runs needed`}
                      formatter={(value, key) => [
                        `${Number(value).toFixed(0)}%`,
                        key === "won"
                          ? `${name(batting)} win`
                          : key === "lost"
                            ? `${name(fielding)} win`
                            : "Draw",
                      ]}
                    />
                    <Area
                      dataKey="won"
                      stackId="c"
                      stroke="none"
                      fill={SIDE_COLORS.a}
                      fillOpacity={0.55}
                      isAnimationActive={false}
                    />
                    <Area
                      dataKey="drawn"
                      stackId="c"
                      stroke="none"
                      fill={DRAW_COLOR}
                      fillOpacity={0.25}
                      isAnimationActive={false}
                    />
                    <Area
                      dataKey="lost"
                      stackId="c"
                      stroke="none"
                      fill={SIDE_COLORS.b}
                      fillOpacity={0.55}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Runs needed across the bottom, with {wickets} wickets in hand and {overs} overs
                left. The dashed line is the chase above.
              </p>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
