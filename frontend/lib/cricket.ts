/**
 * Cricket display helpers. Mirrors `criciq_core.cricket` so the UI and the API
 * agree on overs notation and rates. All inputs are *legal* balls.
 */

export function oversNotation(legalBalls: number, ballsPerOver = 6): string {
  if (!Number.isInteger(legalBalls) || legalBalls < 0) {
    throw new RangeError("legalBalls must be a non-negative integer");
  }
  const completed = Math.floor(legalBalls / ballsPerOver);
  return `${completed}.${legalBalls % ballsPerOver}`;
}

export function runRate(runs: number, legalBalls: number, ballsPerOver = 6): number | null {
  if (legalBalls <= 0) return null;
  return (runs * ballsPerOver) / legalBalls;
}

export function requiredRunRate(
  runsNeeded: number,
  ballsRemaining: number,
  ballsPerOver = 6,
): number | null {
  if (runsNeeded <= 0) return null;
  if (ballsRemaining <= 0) return Infinity;
  return (runsNeeded * ballsPerOver) / ballsRemaining;
}

/** Rates are shown to two decimals; "—" when undefined, "∞" when unreachable. */
export function formatRate(rate: number | null): string {
  if (rate === null) return "—";
  if (!Number.isFinite(rate)) return "∞";
  return rate.toFixed(2);
}
