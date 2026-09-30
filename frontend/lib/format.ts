const DATE_FORMAT = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/** "2019-05-12" -> "12 May 2019" (dates are calendar dates, so format in UTC). */
export function formatDate(iso: string): string {
  return DATE_FORMAT.format(new Date(`${iso}T00:00:00Z`));
}

/** "146/4", or "—" when the side did not bat. */
export function formatScore(runs: number | null | undefined, wickets: number | null | undefined) {
  if (runs === null || runs === undefined) return "—";
  return wickets === 10 ? String(runs) : `${runs}/${wickets ?? 0}`;
}

export function inningsLabel(inningsNo: number, isSuperOver: boolean): string {
  if (isSuperOver) return `Super over ${Math.ceil((inningsNo - 2) / 2)}`;
  return inningsNo === 1 ? "1st innings" : "2nd innings";
}

export function stageLabel(stage: string, matchNumber: number | null | undefined): string {
  return stage === "League" ? (matchNumber ? `Match ${matchNumber}` : "League") : stage;
}
