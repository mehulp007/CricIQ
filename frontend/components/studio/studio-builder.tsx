"use client";

import { Check, Copy, Download, ExternalLink, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";

import {
  DataStep,
  Field,
  MeasuresStep,
  Step,
  StyleStep,
} from "@/components/studio/studio-controls";
import {
  MatchCard,
  matchRows,
  matchSubtitle,
  matchTitle,
  StudioChart,
} from "@/components/studio/studio-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { MatchDetail, StudioOptions, StudioResult, StudioSpec } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { downloadCsv, downloadPng, downloadSvg, svgDocument } from "@/lib/export-image";
import {
  csvTable,
  defaultSubtitle,
  defaultTitle,
  deleteDesign,
  designsSnapshot,
  normalizeSpec,
  parseDesigns,
  parseState,
  rowLabel,
  saveDesign,
  stateToParams,
  subscribeDesigns,
  templateState,
  TEMPLATES,
  type StudioState,
  type StudioStyle,
  type TemplateKey,
} from "@/lib/studio";
import { cn } from "@/lib/utils";

const FETCH_DELAY_MS = 250;

export interface MatchChoice {
  value: string;
  label: string;
}

function namesFrom(result: StudioResult | null): Record<string, string> {
  const names: Record<string, string> = {};
  for (const row of [...(result?.rows ?? []), ...(result?.series ?? [])]) {
    if (row.group?.player_id) names[row.group.player_id] = row.group.label;
  }
  return names;
}

/**
 * Chart Studio: pick a template or build a spec step by step, see it drawn, and export it
 * as PNG, SVG or CSV. The whole design lives in the URL (an image you add stays in the
 * browser), so "Copy link" shares the same chart.
 */
export function StudioBuilder({
  competition,
  competitionLabel,
  teamWord,
  options,
  initial,
  initialResult,
  initialMatch,
  matches,
  footerSpan,
}: {
  competition: string;
  competitionLabel: string;
  teamWord: string;
  options: StudioOptions;
  initial: StudioState;
  initialResult: StudioResult | null;
  initialMatch: MatchDetail | null;
  matches: MatchChoice[];
  footerSpan: string;
}) {
  const [state, setState] = useState<StudioState>(initial);
  const [result, setResult] = useState<StudioResult | null>(initialResult);
  const [match, setMatch] = useState<MatchDetail | null>(initialMatch);
  const [status, setStatus] = useState<"idle" | "loading" | "error">(
    initialResult || initial.template === "match" ? "idle" : "error",
  );
  const [error, setError] = useState<string | null>(null);
  const [names, setNames] = useState<Record<string, string>>(() => namesFrom(initialResult));
  const [image, setImage] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [designName, setDesignName] = useState("");
  const svgRef = useRef<SVGSVGElement>(null);
  // The spec the shown result is for, so an unchanged spec isn't fetched again.
  const [resultKey, setResultKey] = useState(() => JSON.stringify(initial.spec));
  // While a new template's figures load, the old ones keep the chart they were drawn as.
  const [heldChart, setHeldChart] = useState<StudioStyle["chart"] | null>(null);
  const nameId = useId();

  const isMatch = state.template === "match";
  const specKey = JSON.stringify(state.spec);
  const chart = resultKey !== specKey && heldChart ? heldChart : state.style.chart;
  const query = stateToParams(state, options).toString();

  // Keep the URL in step with the design, without a server round trip.
  useEffect(() => {
    const url = `${window.location.pathname}${query ? `?${query}` : ""}`;
    if (url !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(null, "", url);
    }
  }, [query]);

  useEffect(() => {
    if (isMatch || specKey === resultKey) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setStatus("loading");
      try {
        const response = await fetch(`/api/${competition}/studio`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: specKey,
          signal: controller.signal,
        });
        const body = (await response.json()) as StudioResult & { detail?: string };
        if (!response.ok) {
          setError(body.detail ?? "That chart couldn't be built.");
          setStatus("error");
          return;
        }
        setResultKey(specKey);
        setHeldChart(null);
        setResult(body);
        setNames((known) => ({ ...known, ...namesFrom(body) }));
        setError(null);
        setStatus("idle");
      } catch (cause) {
        if ((cause as Error).name === "AbortError") return;
        setError("The data service is waking up. Try again in a moment.");
        setStatus("error");
      }
    }, FETCH_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [competition, isMatch, specKey, resultKey]);

  useEffect(() => {
    if (!isMatch || state.match === null || state.match === match?.summary.match_id) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setStatus("loading");
      try {
        const response = await fetch(`/api/${competition}/studio/match?id=${state.match}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("unavailable");
        setMatch((await response.json()) as MatchDetail);
        setStatus("idle");
      } catch (cause) {
        if ((cause as Error).name === "AbortError") return;
        setError("That match couldn't be loaded.");
        setStatus("error");
      }
    }, 0);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [competition, isMatch, match?.summary.match_id, state.match]);

  const rawDesigns = useSyncExternalStore(subscribeDesigns, designsSnapshot, () => "[]");
  const designs = useMemo(
    () => parseDesigns(rawDesigns).filter((d) => d.competition === competition),
    [rawDesigns, competition],
  );

  function updateSpec(part: Partial<StudioSpec>) {
    setState((s) => ({ ...s, spec: normalizeSpec({ ...s.spec, ...part }, options) }));
  }
  function updateStyle(part: Partial<StudioStyle>) {
    setState((s) => ({ ...s, style: { ...s.style, ...part } }));
  }
  function choosePlayer(id: string, name: string | null) {
    if (name) setNames((known) => ({ ...known, [id]: name }));
    setState((s) => {
      const players = s.spec.filters?.players ?? [];
      const next = name ? [...players, id].slice(0, 6) : players.filter((p) => p !== id);
      return {
        ...s,
        spec: normalizeSpec(
          { ...s.spec, filters: { ...(s.spec.filters ?? {}), players: next } },
          options,
        ),
      };
    });
  }
  function chooseTemplate(key: TemplateKey) {
    setError(null);
    if (!isMatch) setHeldChart(chart);
    setState((s) => {
      const next = templateState(key, options);
      const players = s.spec.filters?.players ?? [];
      return {
        ...next,
        spec: players.length
          ? normalizeSpec({ ...next.spec, filters: { ...next.spec.filters, players } }, options)
          : next.spec,
        style: { ...s.style, chart: next.style.chart, title: "", subtitle: "" },
        match: key === "match" ? (s.match ?? (matches[0] ? Number(matches[0].value) : null)) : null,
      };
    });
  }

  const shown = isMatch ? null : result;
  const title =
    state.style.title ||
    (isMatch
      ? match
        ? matchTitle(match)
        : "Match card"
      : shown
        ? defaultTitle(shown, competitionLabel)
        : "");
  const subtitle =
    state.style.subtitle ||
    (isMatch ? (match ? matchSubtitle(match) : "") : shown ? defaultSubtitle(shown, options) : "");
  const version = (isMatch ? null : shown?.data_version) ?? options.data_version;
  const footer = `Data: Cricsheet (ODC-BY 1.0) · ${competitionLabel} ${footerSpan} · data ${version}`;
  const empty = !isMatch && shown !== null && shown.rows.length === 0;
  const ready = isMatch ? match !== null : shown !== null && !empty;
  const model = shown?.columns.some((c) => c.model) ?? false;

  function say(text: string) {
    setNotice(text);
    setTimeout(() => setNotice(""), 2500);
  }
  async function exportImage(kind: "png" | "svg") {
    const svg = svgRef.current;
    if (!svg) return;
    try {
      if (kind === "png") await downloadPng(svg, title);
      else await downloadSvg(svg, title);
      say(`Saved the ${kind.toUpperCase()}.`);
    } catch {
      say("This browser couldn't make the image.");
    }
  }
  function exportCsv() {
    if (isMatch && match) {
      downloadCsv(["Innings", "Score", "Top batter", "Top bowler"], matchRows(match), title);
    } else if (shown) {
      const table = csvTable(shown);
      downloadCsv(table.headers, table.rows, title);
    }
    say("Saved the CSV.");
  }
  async function openFull() {
    const svg = svgRef.current;
    if (!svg) return;
    const opened = window.open("", "_blank");
    if (!opened) return;
    const url = URL.createObjectURL(
      new Blob([await svgDocument(svg)], { type: "image/svg+xml;charset=utf-8" }),
    );
    opened.location.href = url;
  }
  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      say("Link copied.");
    } catch {
      say("Copy the address from the address bar.");
    }
  }

  const chartProps = {
    style: { ...state.style, chart },
    title,
    subtitle,
    footer,
    image,
    svgRef,
  };
  const portrait = state.style.size === "portrait";

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] xl:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-7">
        <section aria-labelledby={`${nameId}-templates`} className="flex flex-col gap-2">
          <h2 id={`${nameId}-templates`} className="text-sm font-semibold tracking-tight">
            Start from a template
          </h2>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Templates">
            {TEMPLATES.map((t) => (
              <button
                key={t.key}
                type="button"
                aria-pressed={state.template === t.key}
                title={t.description}
                onClick={() => chooseTemplate(t.key)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs transition-colors",
                  state.template === t.key
                    ? "border-primary bg-primary/15 text-foreground"
                    : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {TEMPLATES.find((t) => t.key === state.template)?.description}
          </p>
        </section>

        {isMatch ? (
          <Step number={1} title="Match">
            {matches.length ? (
              <Field
                label="Match"
                value={state.match === null ? matches[0].value : String(state.match)}
                choices={matches}
                onChange={(v) => setState((s) => ({ ...s, match: Number(v) }))}
              />
            ) : (
              <p className="text-sm text-muted-foreground">No matches in this competition yet.</p>
            )}
          </Step>
        ) : (
          <>
            <DataStep
              state={state}
              options={options}
              names={names}
              teamWord={teamWord}
              onSpec={updateSpec}
              onPlayer={choosePlayer}
            />
            <MeasuresStep state={state} options={options} onSpec={updateSpec} />
          </>
        )}
        <StyleStep
          style={state.style}
          image={image}
          onStyle={updateStyle}
          onImage={(next, problem) => {
            setImage(next);
            if (problem) say(problem);
          }}
        />

        <Step number={4} title="Save this design">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const name = designName.trim().slice(0, 60);
              if (!name) return;
              say(
                saveDesign({ name, competition, query })
                  ? `Saved “${name}” in this browser.`
                  : "This browser won't store designs (private mode?).",
              );
              setDesignName("");
            }}
          >
            <label htmlFor={`${nameId}-design`} className="sr-only">
              Design name
            </label>
            <input
              id={`${nameId}-design`}
              value={designName}
              onChange={(e) => setDesignName(e.target.value)}
              placeholder="Name this design"
              maxLength={60}
              className="h-9 min-w-0 flex-1 rounded-lg border border-input bg-transparent px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30"
            />
            <Button type="submit" variant="outline" size="lg" disabled={!designName.trim()}>
              <Save aria-hidden="true" />
              Save
            </Button>
          </form>
          {designs.length > 0 && (
            <ul className="flex flex-col divide-y divide-border text-sm" aria-label="Saved designs">
              {designs.map((d) => (
                <li key={d.name} className="flex items-center justify-between gap-2 py-1.5">
                  <button
                    type="button"
                    className="min-w-0 truncate text-left hover:text-primary"
                    onClick={() => {
                      setError(null);
                      setState(parseState(new URLSearchParams(d.query), options));
                    }}
                  >
                    {d.name}
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteDesign(d.name, competition)}
                    className="rounded p-1 text-muted-foreground hover:text-foreground"
                    aria-label={`Delete ${d.name}`}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted-foreground">
            Designs stay in this browser. To share one, copy its link.
          </p>
        </Step>
      </div>

      <div className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-20 lg:self-start">
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Export">
          <Button size="lg" onClick={() => exportImage("png")} disabled={!ready}>
            <Download aria-hidden="true" />
            PNG
          </Button>
          <Button size="lg" variant="outline" onClick={() => exportImage("svg")} disabled={!ready}>
            <Download aria-hidden="true" />
            SVG
          </Button>
          <Button size="lg" variant="outline" onClick={exportCsv} disabled={!ready}>
            <Download aria-hidden="true" />
            CSV
          </Button>
          <Button size="lg" variant="ghost" onClick={openFull} disabled={!ready}>
            <ExternalLink aria-hidden="true" />
            Open
          </Button>
          <Button size="lg" variant="ghost" onClick={copyLink}>
            {notice === "Link copied." ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
            Copy link
          </Button>
          <span className="text-xs text-muted-foreground" role="status" aria-live="polite">
            {status === "loading" ? "Updating…" : notice}
          </span>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm"
          >
            {error}
          </p>
        )}

        {isMatch && !match ? (
          <EmptyState
            title={matches.length ? "Loading the match" : "No matches yet"}
            description="Pick a match to turn its scorecard into an image."
          />
        ) : !isMatch && !shown ? (
          <EmptyState
            title="The chart couldn't be built"
            description="The data service may be waking up. Change any setting to try again."
          />
        ) : empty ? (
          <EmptyState
            title="Nothing qualifies"
            description="No rows match these filters and minimum. Try a wider season range or a lower minimum."
          />
        ) : (
          <Tabs defaultValue="visual" className="min-w-0">
            <TabsList aria-label="Output">
              <TabsTrigger value="visual">Visual</TabsTrigger>
              <TabsTrigger value="table">Table</TabsTrigger>
              {!isMatch && <TabsTrigger value="sql">SQL</TabsTrigger>}
            </TabsList>
            <TabsContent value="visual" forceMount className="data-[state=inactive]:hidden">
              <div
                className={cn(
                  "transition-opacity",
                  status === "loading" && "opacity-60",
                  portrait && "mx-auto max-w-sm",
                )}
              >
                {isMatch && match ? (
                  <MatchCard match={match} {...chartProps} />
                ) : shown ? (
                  <StudioChart result={shown} {...chartProps} />
                ) : null}
              </div>
              {model && (
                <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">Model estimate</Badge>
                  Win probability added comes from CricIQ&apos;s win probability model.
                </p>
              )}
            </TabsContent>
            <TabsContent value="table">
              {isMatch && match ? (
                <MatchTable match={match} />
              ) : shown ? (
                <ResultTable result={shown} competition={competition} />
              ) : null}
            </TabsContent>
            {!isMatch && shown && (
              <TabsContent value="sql">
                <SqlView result={shown} />
              </TabsContent>
            )}
          </Tabs>
        )}
        {shown?.truncated && (
          <p className="text-xs text-muted-foreground">
            More rows qualify than the {shown.spec.limit} shown; raise “Rows” to see them.
          </p>
        )}
      </div>
    </div>
  );
}

function ResultTable({ result, competition }: { result: StudioResult; competition: string }) {
  const grouped = Boolean(result.spec.group_by);
  return (
    <div className="relative overflow-x-auto" {...scrollRegion("Chart figures")}>
      <table className="w-full min-w-[28rem] text-sm">
        <thead className="border-b border-border">
          <tr className="text-xs text-muted-foreground">
            {grouped && (
              <th scope="col" className="w-10 px-2 py-2 text-left font-medium">
                #
              </th>
            )}
            <th scope="col" className="sticky left-0 bg-background px-2 py-2 text-left font-medium">
              {result.group_label ?? "All"}
            </th>
            {result.columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className="px-2 py-2 text-right font-medium"
                title={c.description}
              >
                {c.label}
              </th>
            ))}
            <th scope="col" className="px-2 py-2 text-right font-medium capitalize">
              {result.sample_label}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border font-mono tabular-nums">
          {result.rows.map((r, i) => (
            <tr key={r.group?.key ?? i}>
              {grouped && (
                <td className="px-2 py-1.5 text-muted-foreground">
                  {r.rank === null || r.rank === undefined ? "" : `${r.tied ? "=" : ""}${r.rank}`}
                </td>
              )}
              <th
                scope="row"
                className="sticky left-0 bg-background px-2 py-1.5 text-left font-sans font-normal"
              >
                {r.group?.player_id ? (
                  <Link
                    href={`/${competition}/players/${r.group.player_id}`}
                    prefetch={false}
                    className="hover:text-primary hover:underline"
                  >
                    {rowLabel(r)}
                  </Link>
                ) : (
                  rowLabel(r)
                )}
              </th>
              {result.columns.map((c) => (
                <td key={c.key} className="px-2 py-1.5 text-right">
                  {r.display[c.key]}
                </td>
              ))}
              <td className="px-2 py-1.5 text-right text-muted-foreground">
                {r.sample.toLocaleString("en-US")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.split_label && (
        <p className="mt-2 text-xs text-muted-foreground">
          Each {result.group_label?.toLowerCase()}&apos;s row covers every{" "}
          {result.split_label.toLowerCase()}; the chart and the CSV split it into series.
        </p>
      )}
    </div>
  );
}

function MatchTable({ match }: { match: MatchDetail }) {
  return (
    <div className="relative overflow-x-auto" {...scrollRegion("Match card figures")}>
      <table className="w-full min-w-[28rem] text-sm">
        <thead className="border-b border-border">
          <tr className="text-xs text-muted-foreground">
            {["Innings", "Score", "Top batter", "Top bowler"].map((h) => (
              <th key={h} scope="col" className="px-2 py-2 text-left font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {matchRows(match).map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-1.5">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SqlView({ result }: { result: StudioResult }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        The query that computed these figures. Each ? is a value from your choices, sent separately:{" "}
        {result.params.length ? result.params.map(String).join(", ") : "none"}.
      </p>
      <pre
        className="max-h-[32rem] overflow-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed"
        {...scrollRegion("Query")}
      >
        <code>{result.sql}</code>
      </pre>
      <div>
        <Button
          variant="outline"
          size="lg"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(result.sql);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copied ? "Copied" : "Copy query"}
        </Button>
      </div>
    </div>
  );
}
