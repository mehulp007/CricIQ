import Link from "next/link";

import type { Rating, RatingGroup } from "@/lib/api/types";
import { PLAYER_SERIES, STABILITY_LABELS, formatRatingValue, ratingBand } from "@/lib/players";
import { cn } from "@/lib/utils";

/**
 * One rating on a 0-100 track: the 90% interval as a band, the estimate as a
 * dot, and a tick at 50 (a typical qualified player).
 */
export function RatingTrack({
  item,
  color,
  name,
  className,
}: {
  item: Rating;
  color: string;
  name?: string;
  className?: string;
}) {
  const who = name ? `${name}, ${item.label}` : item.label;
  const label =
    item.rating === null || item.rating === undefined
      ? `${who}: not rated, too few ${item.exposure_unit}`
      : `${who}: ${item.rating} out of 100, 90% interval ${item.low} to ${item.high}`;
  return (
    <span className={cn("relative block h-3", className)} role="img" aria-label={label}>
      <span
        aria-hidden="true"
        className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted"
      />
      <span aria-hidden="true" className="absolute -inset-y-0.5 left-1/2 w-px bg-foreground/30" />
      {item.rating !== null && item.rating !== undefined && (
        <>
          <span
            aria-hidden="true"
            className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full opacity-30"
            style={{
              left: `${item.low ?? item.rating}%`,
              width: `${Math.max((item.high ?? item.rating) - (item.low ?? item.rating), 1)}%`,
              background: color,
            }}
          />
          <span
            aria-hidden="true"
            className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
            style={{ left: `${item.rating}%`, background: color }}
          />
        </>
      )}
    </span>
  );
}

export function RatingNumber({ item }: { item: Rating }) {
  if (item.rating === null || item.rating === undefined) {
    return (
      <span
        className="text-xs text-muted-foreground"
        title={`Too few ${item.exposure_unit} (${item.exposure}) to rate`}
      >
        n/a
      </span>
    );
  }
  return (
    <span className="flex flex-col items-end leading-tight">
      <span className="font-mono text-sm font-semibold tabular-nums">{item.rating}</span>
      <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
        {item.low}–{item.high}
      </span>
    </span>
  );
}

export function StabilityNote({ item }: { item: Rating }) {
  if (item.stability !== "low") return null;
  return (
    <span
      className="ml-2 rounded border border-dashed border-border px-1.5 py-px text-[10px] tracking-wide text-muted-foreground uppercase"
      title={`${STABILITY_LABELS.low}: a single season's rating barely predicts the next.`}
    >
      Low stability
    </span>
  );
}

function exposure(item: Rating): string {
  return `${item.exposure.toLocaleString("en-IN")} ${item.exposure_unit}`;
}

export function RatingBars({
  group,
  noun,
  window,
}: {
  group: RatingGroup;
  noun: "batters" | "bowlers";
  window: string;
}) {
  return (
    <div className="flex flex-col gap-4">
      {!group.qualified && (
        <p className="rounded-lg border border-dashed border-border px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          Below the {group.min_balls}-ball mark in these seasons ({group.balls} balls), so the
          ratings lean heavily on the average and the intervals are wide.
        </p>
      )}
      <ul className="flex flex-col gap-4">
        {group.items.map((item) => (
          <li
            key={item.key}
            className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_12rem_3rem] sm:items-center sm:gap-4"
          >
            <div className="min-w-0">
              <p className="text-sm" title={item.description}>
                {item.label}
                {item.rating !== null && item.rating !== undefined && (
                  <span className="sr-only">, {ratingBand(item.rating).toLowerCase()}</span>
                )}
                <StabilityNote item={item} />
              </p>
              <p
                className="font-mono text-xs text-muted-foreground tabular-nums"
                title={`Own record ${formatRatingValue(item.raw, item.unit)}; qualified average ${formatRatingValue(item.average, item.unit)}. The record carries ${Math.round(item.weight * 100)}% of the estimate.`}
              >
                {formatRatingValue(item.value, item.unit)} · {exposure(item)}
              </p>
            </div>
            <div className="flex items-center gap-3 sm:contents">
              <RatingTrack item={item} color={PLAYER_SERIES.player.color} className="flex-1" />
              <span className="w-12 text-right">
                <RatingNumber item={item} />
              </span>
            </div>
          </li>
        ))}
      </ul>
      <p className="text-xs leading-relaxed text-muted-foreground">
        0–100 against {group.population} {noun} with {group.min_balls}+ balls in {window}; 50 (the
        tick) is a typical one. Each record is first blended with the average according to how much
        a record of that size can be trusted, and the band is the 90% interval.{" "}
        <Link href="/about#ratings" className="text-foreground underline-offset-4 hover:underline">
          How ratings work
        </Link>
        .
      </p>
    </div>
  );
}
