"use client";

import { ImagePlus, X } from "lucide-react";
import { useId, type ReactNode } from "react";

import { PlayerPicker } from "@/components/matchups/player-picker";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CHART_SIZES, CHART_THEMES } from "@/components/charts/svg/theme";
import type { StudioDataset, StudioOptions, StudioSpec } from "@/lib/api/types";
import {
  CHART_TYPES,
  normalizeSpec,
  STUDIO_THEMES,
  type ChartType,
  type StudioState,
  type StudioStyle,
} from "@/lib/studio";
import { cn } from "@/lib/utils";

const NONE = "none";
const AUTO = "auto";
const MAX_IMAGE_BYTES = 2_000_000;

const inputClass =
  "h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30";

export function Step({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="flex items-center gap-2 text-sm font-semibold tracking-tight">
        <span
          className="flex size-6 items-center justify-center rounded-full bg-primary/15 font-mono text-xs text-primary"
          aria-hidden="true"
        >
          {number}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

/** A labelled select (choices' values must not be empty). */
export function Field({
  label,
  value,
  choices,
  onChange,
  className,
}: {
  label: string;
  value: string;
  choices: { value: string; label: string }[];
  onChange: (value: string) => void;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <span id={id} className="text-xs text-muted-foreground">
        {label}
      </span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-full" aria-labelledby={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {choices.map((c) => (
            <SelectItem key={c.value} value={c.value}>
              {c.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (Number.isFinite(n)) onChange(Math.min(max, Math.max(min, Math.round(n))));
        }}
        className={cn(inputClass, "font-mono tabular-nums")}
      />
    </div>
  );
}

function TextField({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        type="text"
        maxLength={120}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </div>
  );
}

const choice = (value: string | number | null | undefined) =>
  value === null || value === undefined ? NONE : String(value);
const fromChoice = (value: string) => (value === NONE ? null : value);
const intChoice = (value: string) => (value === NONE ? null : Number(value));

function inningsChoices(dataset: StudioDataset, format: StudioOptions["format"]) {
  if (dataset.key === "teams") {
    return [
      { value: "1", label: "Batting first" },
      { value: "2", label: "Batting second" },
    ];
  }
  const count = format === "Test" ? 4 : 2;
  const names = ["1st innings", "2nd innings", "3rd innings", "4th innings"];
  return names.slice(0, count).map((label, i) => ({ value: String(i + 1), label }));
}

/** Step 1: the dataset, players and filters. */
export function DataStep({
  state,
  options,
  names,
  teamWord,
  onSpec,
  onPlayer,
}: {
  state: StudioState;
  options: StudioOptions;
  names: Record<string, string>;
  teamWord: string;
  onSpec: (spec: Partial<StudioSpec>) => void;
  onPlayer: (id: string, name: string | null) => void;
}) {
  const spec = state.spec;
  const dataset = options.datasets.find((d) => d.key === spec.dataset) ?? options.datasets[0];
  const allowed = new Set(dataset.filters);
  const f = spec.filters ?? { players: [] };
  const players = f.players ?? [];
  const filter = (part: Partial<NonNullable<StudioSpec["filters"]>>) =>
    onSpec({ filters: { ...f, ...part, players } });
  const seasons = options.seasons.map((s) => ({ value: s.value, label: s.label }));

  return (
    <Step number={1} title="Data">
      <Field
        label="Dataset"
        value={spec.dataset}
        choices={options.datasets.map((d) => ({ value: d.key, label: d.label }))}
        onChange={(v) =>
          onSpec(normalizeSpec({ ...spec, dataset: v as StudioSpec["dataset"] }, options))
        }
      />
      <p className="text-xs text-muted-foreground">{dataset.description}</p>

      {allowed.has("players") && (
        <div className="flex flex-col gap-2">
          {players.length < 6 ? (
            <PlayerPicker
              label={`Players (${players.length} of 6)`}
              value={null}
              role="batter"
              placeholder="Search a player"
              onChange={(p) => p && !players.includes(p.player_id) && onPlayer(p.player_id, p.name)}
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              Six players chosen (the most a chart takes).
            </p>
          )}
          {players.length > 0 && (
            <ul className="flex flex-wrap gap-1.5" aria-label="Chosen players">
              {players.map((id) => (
                <li key={id}>
                  <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 py-0.5 pr-1 pl-2.5 text-xs">
                    {names[id] ?? id}
                    <button
                      type="button"
                      onClick={() => onPlayer(id, null)}
                      className="rounded-full p-0.5 text-muted-foreground hover:text-foreground"
                      aria-label={`Remove ${names[id] ?? id}`}
                    >
                      <X className="size-3.5" aria-hidden="true" />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {allowed.has("team") && (
          <Field
            label={teamWord}
            value={choice(f.team)}
            choices={[{ value: NONE, label: `Every ${teamWord.toLowerCase()}` }, ...options.teams]}
            onChange={(v) => filter({ team: fromChoice(v) })}
          />
        )}
        {allowed.has("opponent") && (
          <Field
            label="Opponent"
            value={choice(f.opponent)}
            choices={[{ value: NONE, label: "Every opponent" }, ...options.teams]}
            onChange={(v) => filter({ opponent: fromChoice(v) })}
          />
        )}
        {allowed.has("season") && (
          <>
            <Field
              label="From season"
              value={choice(f.season_from)}
              choices={[{ value: NONE, label: "First" }, ...seasons]}
              onChange={(v) => filter({ season_from: intChoice(v) })}
            />
            <Field
              label="To season"
              value={choice(f.season_to)}
              choices={[{ value: NONE, label: "Latest" }, ...seasons]}
              onChange={(v) => filter({ season_to: intChoice(v) })}
            />
          </>
        )}
        {allowed.has("venue") && (
          <Field
            className="col-span-2"
            label="Ground"
            value={choice(f.venue)}
            choices={[{ value: NONE, label: "Every ground" }, ...options.grounds]}
            onChange={(v) => filter({ venue: fromChoice(v) })}
          />
        )}
        {allowed.has("innings") && (
          <Field
            label="Innings"
            value={choice(f.innings)}
            choices={[
              { value: NONE, label: "Every innings" },
              ...inningsChoices(dataset, options.format),
            ]}
            onChange={(v) => filter({ innings: intChoice(v) })}
          />
        )}
        {allowed.has("position") && (
          <Field
            label="Batting position"
            value={choice(f.position)}
            choices={[
              { value: NONE, label: "Any position" },
              ...Array.from({ length: 11 }, (_, i) => ({
                value: String(i + 1),
                label: `No. ${i + 1}`,
              })),
            ]}
            onChange={(v) => filter({ position: intChoice(v) })}
          />
        )}
        {allowed.has("phase") && (
          <Field
            label="Phase"
            value={choice(f.phase)}
            choices={[{ value: NONE, label: "Every phase" }, ...options.phases]}
            onChange={(v) => filter({ phase: fromChoice(v) })}
          />
        )}
      </div>
    </Step>
  );
}

/** Step 2: measures, grouping, sort and qualification. */
export function MeasuresStep({
  state,
  options,
  onSpec,
}: {
  state: StudioState;
  options: StudioOptions;
  onSpec: (spec: Partial<StudioSpec>) => void;
}) {
  const id = useId();
  const spec = state.spec;
  const dataset = options.datasets.find((d) => d.key === spec.dataset) ?? options.datasets[0];
  const chosen = spec.measures;
  const group = spec.group_by ?? null;
  const natural = dataset.dimensions.find((d) => d.key === group)?.natural ?? false;
  const labelOf = (key: string) => dataset.measures.find((m) => m.key === key)?.label ?? key;

  function toggle(key: string) {
    const next = chosen.includes(key) ? chosen.filter((m) => m !== key) : [...chosen, key];
    if (next.length === 0 || next.length > 6) return;
    onSpec({
      measures: next,
      sort: spec.sort && !next.includes(spec.sort) && spec.sort !== "group" ? null : spec.sort,
    });
  }

  return (
    <Step number={2} title="Measures">
      <fieldset className="flex flex-col gap-1.5">
        <legend id={id} className="mb-1.5 text-xs text-muted-foreground">
          Up to six; the first ranks the rows unless you choose a sort.
        </legend>
        <div className="grid grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-2">
          {dataset.measures.map((m) => {
            const on = chosen.includes(m.key);
            return (
              <label
                key={m.key}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-muted/60",
                  !on && chosen.length >= 6 && "opacity-50",
                )}
                title={m.description}
              >
                <input
                  type="checkbox"
                  checked={on}
                  disabled={(!on && chosen.length >= 6) || (on && chosen.length === 1)}
                  onChange={() => toggle(m.key)}
                  className="size-4 accent-[var(--primary)]"
                />
                <span className="min-w-0 truncate">{m.label}</span>
                {on && (
                  <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                    {chosen.indexOf(m.key) + 1}
                  </span>
                )}
                {m.model && (
                  <Badge variant="outline" className="shrink-0 text-[10px]">
                    Model
                  </Badge>
                )}
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <Field
          label="Group by"
          value={group ?? NONE}
          choices={[
            ...dataset.dimensions.map((d) => ({ value: d.key, label: d.label })),
            ...(dataset.needs_player ? [] : [{ value: NONE, label: "Overall (one row)" }]),
          ]}
          onChange={(v) =>
            onSpec({
              group_by: v === NONE ? null : (v as StudioSpec["group_by"]),
              split_by: v === NONE || v === spec.split_by ? null : spec.split_by,
              sort: spec.sort === "group" ? null : spec.sort,
            })
          }
        />
        <Field
          label="Split into series"
          value={spec.split_by ?? NONE}
          choices={[
            { value: NONE, label: "No split" },
            ...dataset.dimensions
              .filter((d) => d.key !== group)
              .map((d) => ({ value: d.key, label: d.label })),
          ]}
          onChange={(v) =>
            group !== null &&
            onSpec({ split_by: v === NONE ? null : (v as StudioSpec["split_by"]) })
          }
        />
        <Field
          label="Sort by"
          value={spec.sort ?? AUTO}
          choices={[
            {
              value: AUTO,
              label: natural ? "Grouping's order" : `Automatic (${labelOf(chosen[0])})`,
            },
            ...chosen.map((m) => ({ value: m, label: labelOf(m) })),
            ...(natural ? [{ value: "group", label: "Grouping's order" }] : []),
          ]}
          onChange={(v) => onSpec({ sort: v === AUTO ? null : v })}
        />
        <Field
          label="Order"
          value={spec.order ?? AUTO}
          choices={[
            { value: AUTO, label: "Automatic" },
            {
              value: "desc",
              label:
                natural && (spec.sort ?? "group") === "group" ? "Latest first" : "Highest first",
            },
            {
              value: "asc",
              label:
                natural && (spec.sort ?? "group") === "group" ? "Earliest first" : "Lowest first",
            },
          ]}
          onChange={(v) => onSpec({ order: v === AUTO ? null : (v as StudioSpec["order"]) })}
        />
        <NumberField
          label={`Minimum ${dataset.sample_label}`}
          value={spec.min_sample ?? 0}
          min={0}
          max={1_000_000}
          onChange={(v) => onSpec({ min_sample: v })}
        />
        <NumberField
          label="Rows (up to 50)"
          value={spec.limit ?? 15}
          min={1}
          max={50}
          onChange={(v) => onSpec({ limit: v })}
        />
      </div>
      {spec.split_by && (
        <div className="grid grid-cols-2 items-end gap-3">
          <NumberField
            label={`Series (up to ${options.max_series})`}
            value={spec.series ?? options.max_series}
            min={1}
            max={options.max_series}
            onChange={(v) => onSpec({ series: v })}
          />
          <p className="pb-1 text-xs text-muted-foreground">
            The leading series by the first measure (or the players you pick).
          </p>
        </div>
      )}
    </Step>
  );
}

/** Step 3: chart type, size, theme, colour, titles and an image of your own. */
export function StyleStep({
  style,
  image,
  onStyle,
  onImage,
}: {
  style: StudioStyle;
  image: string | null;
  onStyle: (style: Partial<StudioStyle>) => void;
  onImage: (image: string | null, error?: string) => void;
}) {
  const fileId = useId();
  const accentId = useId();
  const labelsId = useId();
  return (
    <Step number={3} title="Style">
      <div className="grid grid-cols-2 gap-3">
        <Field
          label="Chart"
          value={style.chart}
          choices={CHART_TYPES}
          onChange={(v) => onStyle({ chart: v as ChartType })}
        />
        <Field
          label="Size"
          value={style.size}
          choices={Object.entries(CHART_SIZES).map(([value, s]) => ({ value, label: s.label }))}
          onChange={(v) => onStyle({ size: v as StudioStyle["size"] })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-xs text-muted-foreground">Theme</span>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Theme">
          {STUDIO_THEMES.map((name) => {
            const t = CHART_THEMES[name];
            return (
              <button
                key={name}
                type="button"
                aria-pressed={style.theme === name}
                onClick={() => onStyle({ theme: name })}
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs",
                  style.theme === name
                    ? "border-primary ring-2 ring-primary/30"
                    : "border-border hover:border-foreground/30",
                )}
              >
                <span
                  className="size-4 rounded-sm border border-border"
                  style={{ background: t.background, boxShadow: `inset -6px 0 0 ${t.series[0]}` }}
                  aria-hidden="true"
                />
                {t.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor={accentId} className="text-xs text-muted-foreground">
            Accent colour
          </label>
          <input
            id={accentId}
            type="color"
            value={style.accent ?? CHART_THEMES[style.theme].series[0]}
            onChange={(e) => onStyle({ accent: e.target.value })}
            className="h-9 w-14 cursor-pointer rounded-lg border border-input bg-transparent p-1"
          />
        </div>
        {style.accent && (
          <button
            type="button"
            onClick={() => onStyle({ accent: null })}
            className="h-9 rounded-lg px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Theme colour
          </button>
        )}
        <label htmlFor={labelsId} className="flex h-9 items-center gap-2 text-sm">
          <input
            id={labelsId}
            type="checkbox"
            checked={style.labels}
            onChange={(e) => onStyle({ labels: e.target.checked })}
            className="size-4 accent-[var(--primary)]"
          />
          Value labels
        </label>
      </div>
      <TextField
        label="Title"
        value={style.title}
        placeholder="Automatic"
        onChange={(v) => onStyle({ title: v })}
      />
      <TextField
        label="Subtitle"
        value={style.subtitle}
        placeholder="Automatic"
        onChange={(v) => onStyle({ subtitle: v })}
      />
      <div className="flex flex-col gap-1.5">
        <span className="text-xs text-muted-foreground">Your own image</span>
        <div className="flex items-center gap-2">
          <label
            htmlFor={fileId}
            className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-input px-3 text-sm focus-within:ring-[3px] focus-within:ring-ring/50 hover:bg-muted/60"
          >
            <ImagePlus className="size-4" aria-hidden="true" />
            {image ? "Change image" : "Add an image"}
            <input
              id={fileId}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (!file) return;
                if (file.size > MAX_IMAGE_BYTES) {
                  onImage(image, "That image is over 2 MB; try a smaller one.");
                  return;
                }
                const reader = new FileReader();
                reader.onload = () => typeof reader.result === "string" && onImage(reader.result);
                reader.onerror = () => onImage(image, "That image couldn't be read.");
                reader.readAsDataURL(file);
              }}
            />
          </label>
          {image && (
            <button
              type="button"
              onClick={() => onImage(null)}
              className="h-9 rounded-lg px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              Remove image
            </button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          It stays in your browser: it is never uploaded, and links don&apos;t carry it.
        </p>
      </div>
    </Step>
  );
}
