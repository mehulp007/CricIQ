"use client";

import { Dices } from "lucide-react";
import { useState } from "react";

import { SimResults } from "@/components/simulator/sim-results";
import { type TeamOption, XIEditor } from "@/components/simulator/xi-editor";
import type { SimulationResult, SimXI } from "@/lib/api/types";
import {
  type BatFirst,
  DEFAULT_SIMULATIONS,
  SIM_SERIES,
  type XIState,
  sideIssue,
  simulationRequest,
} from "@/lib/simulator";
import { cn } from "@/lib/utils";

function fromXI(xi: SimXI | null): XIState {
  return xi
    ? { team: xi.team?.franchise_id ?? null, players: xi.players, bowlers: xi.bowlers }
    : { team: null, players: [], bowlers: [] };
}

function syncUrl(a: string | null, b: string | null) {
  const params = new URLSearchParams();
  if (a) params.set("a", a);
  if (b) params.set("b", b);
  window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
}

export function SimulatorApp({
  teams,
  initialA,
  initialB,
}: {
  teams: TeamOption[];
  initialA: SimXI | null;
  initialB: SimXI | null;
}) {
  const [a, setA] = useState<XIState>(() => fromXI(initialA));
  const [b, setB] = useState<XIState>(() => fromXI(initialB));
  const [loadingTeam, setLoadingTeam] = useState<"a" | "b" | null>(null);
  const [batFirst, setBatFirst] = useState<BatFirst>("toss");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [status, setStatus] = useState<"idle" | "running" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const nameOf = (xi: XIState, fallback: string) =>
    teams.find((t) => t.id === xi.team)?.name ?? fallback;

  async function pickTeam(side: "a" | "b", team: string) {
    setLoadingTeam(side);
    try {
      const response = await fetch(`/api/simulate/xi?team=${encodeURIComponent(team)}`);
      if (!response.ok) throw new Error(String(response.status));
      const xi = fromXI((await response.json()) as SimXI);
      if (side === "a") {
        setA(xi);
        syncUrl(team, b.team);
      } else {
        setB(xi);
        syncUrl(a.team, team);
      }
      setResult(null);
    } catch {
      setError("Could not load that team's XI. The API may be waking up; try again.");
    } finally {
      setLoadingTeam(null);
    }
  }

  async function run() {
    setStatus("running");
    setError(null);
    try {
      const response = await fetch("/api/simulate/match", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(simulationRequest(a, b, batFirst)),
      });
      const body = (await response.json()) as SimulationResult & { detail?: string };
      if (!response.ok) throw new Error(body.detail ?? String(response.status));
      setResult(body);
      setStatus("idle");
    } catch (e) {
      setError(
        e instanceof Error && e.message && !/^\d+$/.test(e.message)
          ? e.message
          : "The simulator is waking up. Try again in a moment.",
      );
      setStatus("error");
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

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 xl:grid-cols-2">
        <XIEditor
          label="Team A"
          color={SIM_SERIES.a.color}
          teams={teams}
          xi={a}
          busy={loadingTeam === "a"}
          onTeam={(t) => pickTeam("a", t)}
          onChange={(xi) => {
            setA(xi);
            setResult(null);
          }}
        />
        <XIEditor
          label="Team B"
          color={SIM_SERIES.b.color}
          teams={teams}
          xi={b}
          busy={loadingTeam === "b"}
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
          disabled={Boolean(blocked) || status === "running"}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <Dices className="size-4" aria-hidden="true" />
          {status === "running"
            ? "Simulating…"
            : `Simulate ${DEFAULT_SIMULATIONS.toLocaleString("en-IN")} matches`}
        </button>
      </div>
      <p className="-mt-3 text-sm text-muted-foreground" aria-live="polite">
        {blocked
          ? `Not ready: ${blocked}`
          : error
            ? error
            : status === "running"
              ? "Playing every match ball by ball…"
              : ""}
      </p>

      {result && <SimResults result={result} />}
    </div>
  );
}
