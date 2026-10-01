import type { MatchupDetail } from "@/lib/api/types";
import { METRICS, READINGS, type Reading, axisFor, formatValue, position } from "@/lib/matchups";

const ORDER: Reading[] = ["raw", "estimate", "expected"];

export function ReadingsLegend() {
  return (
    <ul
      className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground"
      aria-label="Legend"
    >
      {ORDER.map((key) => (
        <li key={key} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="size-2.5 rounded-full"
            style={{ background: READINGS[key].color }}
          />
          {READINGS[key].label}
        </li>
      ))}
    </ul>
  );
}

/**
 * One row per measure, three readings each: the raw head-to-head record with
 * its 90% sampling interval, the shrunk estimate with its 90% interval, and
 * the expectation from each player's overall record. Shrinkage shows up as
 * the estimate's interval sitting between the other two, and much narrower.
 */
export function ReadingsChart({ detail }: { detail: MatchupDetail }) {
  return (
    <div className="flex flex-col gap-6">
      {METRICS.map((spec) => {
        const intervals = {
          raw: detail.raw?.[spec.key],
          estimate: detail.estimate?.[spec.key],
          expected: detail.expected?.[spec.key],
        };
        const axis = axisFor(Object.values(intervals));
        return (
          <figure key={spec.key} className="flex flex-col gap-2">
            <figcaption className="text-sm font-medium">{spec.label}</figcaption>
            <ul className="flex flex-col gap-1.5">
              {ORDER.map((key) => {
                const interval = intervals[key];
                if (!interval || interval.value === null || interval.value === undefined) {
                  return null;
                }
                const low = interval.low ?? axis[0];
                const high = interval.high ?? axis[1];
                const showRange = key !== "expected";
                return (
                  <li
                    key={key}
                    className="grid grid-cols-[7.5rem_minmax(0,1fr)_8.5rem] items-center gap-3 sm:grid-cols-[11rem_minmax(0,1fr)_9rem]"
                  >
                    <span className="truncate text-xs text-muted-foreground">
                      {READINGS[key].label}
                    </span>
                    <span
                      className="relative h-5"
                      role="img"
                      aria-label={`${READINGS[key].label}: ${formatValue(interval.value, spec)}${
                        showRange
                          ? `, 90% range ${formatValue(interval.low, spec)} to ${
                              interval.high === null
                                ? "unbounded"
                                : formatValue(interval.high, spec)
                            }`
                          : ""
                      }`}
                    >
                      <span
                        aria-hidden="true"
                        className="absolute inset-x-0 top-1/2 h-px bg-border"
                      />
                      {showRange && (
                        <span
                          aria-hidden="true"
                          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full opacity-45"
                          style={{
                            left: `${position(low, axis)}%`,
                            width: `${Math.max(position(high, axis) - position(low, axis), 0.5)}%`,
                            background: READINGS[key].color,
                          }}
                        />
                      )}
                      <span
                        aria-hidden="true"
                        className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
                        style={{
                          left: `${position(interval.value, axis)}%`,
                          background: READINGS[key].color,
                        }}
                      />
                    </span>
                    <span className="text-right font-mono text-xs tabular-nums">
                      {formatValue(interval.value, spec)}
                      {showRange && (
                        <span className="text-muted-foreground">
                          {" "}
                          ({formatValue(interval.low, spec)}–
                          {interval.high === null ? "∞" : formatValue(interval.high, spec)})
                        </span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </figure>
        );
      })}
    </div>
  );
}
