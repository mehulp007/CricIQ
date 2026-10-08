import { RatingNumber, RatingTrack, StabilityNote } from "@/components/players/ratings";
import type { RatingGroup } from "@/lib/api/types";
import { COMPARE_SERIES, ratingPairs } from "@/lib/compare";
import { formatRatingValue } from "@/lib/players";

export function CompareLegend({ a, b }: { a: string; b: string }) {
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Legend">
      {(
        [
          [a, COMPARE_SERIES.a.color],
          [b, COMPARE_SERIES.b.color],
        ] as const
      ).map(([name, color]) => (
        <li key={name} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="size-2.5 rounded-full"
            style={{ background: color }}
          />
          {name}
        </li>
      ))}
    </ul>
  );
}

/** Both players' ratings on the same 0-100 tracks, one lane each, with 90% intervals. */
export function RatingComparison({
  a,
  b,
  names,
  noun,
  sharedOnly = false,
}: {
  a: RatingGroup | null | undefined;
  b: RatingGroup | null | undefined;
  names: [string, string];
  noun: "batters" | "bowlers";
  sharedOnly?: boolean;
}) {
  const pairs = ratingPairs(a, b, sharedOnly);
  const population = a?.population ?? b?.population ?? 0;
  const minBalls = a?.min_balls ?? b?.min_balls ?? 0;
  return (
    <div className="flex flex-col gap-4">
      <CompareLegend a={names[0]} b={names[1]} />
      <ul className="flex flex-col gap-5">
        {pairs.map((pair) => (
          <li key={pair.key} className="flex flex-col gap-2">
            <p className="text-sm" title={pair.description}>
              {pair.label}
              {(pair.a ?? pair.b) && <StabilityNote item={(pair.a ?? pair.b)!} />}
            </p>
            {(
              [
                [pair.a, names[0], COMPARE_SERIES.a.color],
                [pair.b, names[1], COMPARE_SERIES.b.color],
              ] as const
            ).map(([item, name, color]) => (
              <div
                key={name}
                className="grid grid-cols-[minmax(0,1fr)_3rem] items-center gap-3 sm:grid-cols-[10rem_minmax(0,1fr)_3rem]"
              >
                <span
                  className="hidden truncate font-mono text-xs text-muted-foreground tabular-nums sm:block"
                  title={item ? formatRatingValue(item.value, item.unit) : undefined}
                >
                  {item ? formatRatingValue(item.value, item.unit).split(" ")[0] : "—"}
                  <span className="sr-only"> for {name}</span>
                </span>
                {item ? (
                  <RatingTrack item={item} color={color} name={name} />
                ) : (
                  <span className="text-xs text-muted-foreground">
                    No {noun.slice(0, -1)} record
                  </span>
                )}
                <span className="text-right">{item ? <RatingNumber item={item} /> : null}</span>
              </div>
            ))}
          </li>
        ))}
      </ul>
      <p className="text-xs leading-relaxed text-muted-foreground">
        0–100 against {population} {noun} with {minBalls}+ balls in the same seasons; 50 is typical.
        The left column is each player&apos;s shrunk estimate in the rating&apos;s unit (hover for
        it in full). Overlapping bands mean the data cannot tell the two apart.
      </p>
    </div>
  );
}
