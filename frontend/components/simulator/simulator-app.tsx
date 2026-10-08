"use client";

import { Dices } from "lucide-react";
import { useEffect, useState } from "react";

import { type PickRecord, SimResults } from "@/components/simulator/sim-results";
import { XIEditor } from "@/components/simulator/xi-editor";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SimSeason, SimSquad, SimulationResult } from "@/lib/api/types";
import {
  type BatFirst,
  DEFAULT_SIMULATIONS,
  SIM_SERIES,
  type XIState,
  defaultTeams,
  fromSquad,
  sideIssue,
  simulationRequest,
} from "@/lib/simulator";
import { useCompetition } from "@/components/competition/use-competition";
import { getCompetition, seasonLabel } from "@/lib/competitions";
import { cn } from "@/lib/utils";
import { fetchAwake, wakeSimulator } from "@/lib/wake";

const WAKING =
  "Waking the simulator. The free server sleeps when nobody is using it, so the first request can take up to a minute…";

function syncUrl(season: number | null, a: string | null, b: string | null) {
  const params = new URLSearchParams();
  if (season) params.set("season", String(season));
  if (a) params.set("a", a);
  if (b) params.set("b", b);
  window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
}

export function SimulatorApp({
  seasons,
  initialSeason,
  initialA,
  initialB,
  picks = null,
}: {
  seasons: SimSeason[];
  initialSeason: number | null;
  initialA: SimSquad | null;
  initialB: SimSquad | null;
  /** How this competition's backtest picked winners before a ball was bowled. */
  picks?: PickRecord | null;
}) {
  const [season, setSeason] = useState<number | null>(initialSeason);
  const [a, setA] = useState<XIState>(() => fromSquad(initialA));
  const [b, setB] = useState<XIState>(() => fromSquad(initialB));
  const [loading, setLoading] = useState<"a" | "b" | "both" | null>(null);
  const [batFirst, setBatFirst] = useState<BatFirst>("toss");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [status, setStatus] = useState<"idle" | "running" | "error">("idle");
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const competition = useCompetition();
  // The API sleeps when idle: start waking it while the visitor picks sides.
  useEffect(() => wakeSimulator(), []);

  const current = seasons.find((s) => s.season === season) ?? null;
  const teams = current?.teams ?? [];
  const nameOf = (xi: XIState, fallback: string) =>
    teams.find((t) => t.team.franchise_id === xi.team)?.display_name ?? fallback;

  async function loadSquad(year: number, team: string): Promise<XIState> {
    const response = await fetchAwake(
      `/api/${competition}/simulate/squad?season=${year}&team=${encodeURIComponent(team)}`,
      undefined,
      () => setWaking(true),
    );
    if (!response.ok) throw new Error(String(response.status));
    return fromSquad((await response.json()) as SimSquad);
  }

  async function load(work: () => Promise<void>, which: "a" | "b" | "both") {
    setLoading(which);
    setError(null);
    try {
      await work();
      setResult(null);
    } catch {
      setError("Could not load that squad. Try again in a moment.");
    } finally {
      setLoading(null);
      setWaking(false);
    }
  }

  function pickTeam(side: "a" | "b", team: string) {
    if (season === null) return;
    void load(async () => {
      const xi = await loadSquad(season, team);
      if (side === "a") {
        setA(xi);
        syncUrl(season, team, b.team);
      } else {
        setB(xi);
        syncUrl(season, a.team, team);
      }
    }, side);
  }

  function pickSeason(value: string) {
    const next = seasons.find((s) => s.season === Number(value));
    if (!next) return;
    const [ta, tb] = defaultTeams(next, a.team ?? undefined, b.team ?? undefined);
    void load(async () => {
      const [xa, xb] = await Promise.all([
        ta ? loadSquad(next.season, ta) : null,
        tb ? loadSquad(next.season, tb) : null,
      ]);
      setSeason(next.season);
      setA(xa ?? fromSquad(null));
      setB(xb ?? fromSquad(null));
      syncUrl(next.season, ta, tb);
    }, "both");
  }

  async function run() {
    setStatus("running");
    setError(null);
    try {
      const response = await fetchAwake(
        `/api/${competition}/simulate/match`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(simulationRequest(a, b, batFirst, season)),
        },
        () => setWaking(true),
      );
      const body = (await response.json()) as SimulationResult & { detail?: string };
      if (!response.ok) throw new Error(body.detail ?? String(response.status));
      setResult(body);
      setStatus("idle");
    } catch (e) {
      setError(
        e instanceof Error && e.message && !/^\d+$/.test(e.message)
          ? e.message
          : "The simulator did not respond. Try again in a moment.",
      );
      setStatus("error");
    } finally {
      setWaking(false);
    }
  }

  const blocked = sideIssue(a) ?? sideIssue(b);
  const nameA = nameOf(a, "Team A");
  const nameB = nameOf(b, "Team B");
  const options: [BatFirst, string][] = [
    ["toss", "Toss (half each)"],
    ["a", `${nameA} bat first`],
    ["b", `${nameB} bat first`],
  ];
  const busy = loading !== null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card/70 p-4 sm:flex-row sm:items-center sm:p-5">
        <Select value={season ? String(season) : ""} onValueChange={pickSeason} disabled={busy}>
          <SelectTrigger className="w-36" aria-label="Season">
            <SelectValue placeholder="Season" />
          </SelectTrigger>
          <SelectContent>
            {seasons.map((s) => (
              <SelectItem key={s.season} value={String(s.season)}>
                {getCompetition(competition).label} {seasonLabel(competition, s.season)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          {season
            ? `Both sides and their players come from the ${seasonLabel(competition, season)} squads, and runs come as easily as they did in ${seasonLabel(competition, season)}.`
            : "No seasons are available in this build."}
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <XIEditor
          label="Team A"
          color={SIM_SERIES.a.color}
          season={season}
          teams={teams}
          xi={a}
          busy={loading === "a" || loading === "both"}
          onTeam={(t) => pickTeam("a", t)}
          onChange={(xi) => {
            setA(xi);
            setResult(null);
          }}
        />
        <XIEditor
          label="Team B"
          color={SIM_SERIES.b.color}
          season={season}
          teams={teams}
          xi={b}
          busy={loading === "b" || loading === "both"}
          onTeam={(t) => pickTeam("b", t)}
          onChange={(xi) => {
            setB(xi);
            setResult(null);
          }}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card/70 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Who bats first">
          {options.map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={batFirst === value}
              onClick={() => {
                setBatFirst(value);
                setResult(null);
              }}
              className={cn(
                "h-8 rounded-lg border px-3 text-xs transition-colors",
                batFirst === value
                  ? "border-primary/50 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={run}
          disabled={Boolean(blocked) || status === "running" || busy}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <Dices className="size-4" aria-hidden="true" />
          {status === "running"
            ? "Simulating…"
            : `Simulate ${DEFAULT_SIMULATIONS.toLocaleString("en-IN")} matches`}
        </button>
      </div>
      <p
        className={cn("-mt-3 text-sm", error ? "text-negative" : "text-muted-foreground")}
        aria-live="polite"
      >
        {waking
          ? WAKING
          : blocked
            ? `Not ready: ${blocked}`
            : error
              ? error
              : status === "running"
                ? "Playing every match ball by ball…"
                : ""}
      </p>

      {result && <SimResults result={result} picks={picks} />}
    </div>
  );
}
