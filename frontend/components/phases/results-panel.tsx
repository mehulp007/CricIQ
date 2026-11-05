import { StatTile } from "@/components/players/profile-parts";
import type { ResultSplit, TossDecision } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { fig } from "@/lib/phases";

const pct = (value: number | null) => (value === null ? "—" : `${value.toFixed(1)}%`);

/** Who wins, batting first or second, and what the toss winners chose and got. */
export function ResultsPanel({
  results,
  toss,
  test,
  team,
}: {
  results: ResultSplit;
  toss: TossDecision[];
  test: boolean;
  /** The team filtered to, if any (its own matches). */
  team: string | null;
}) {
  const who = team ? `${team} won` : "Won";
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Matches" value={results.matches.toLocaleString("en-US")}>
          {test ? "With a result or drawn" : "With a result (super overs count)"}
        </StatTile>
        <StatTile label={`${who} batting first`} value={pct(results.batting_first.win_pct)}>
          {results.batting_first.won} of {results.batting_first.matches}
          {test && ` · ${results.batting_first.drawn} drawn`}
        </StatTile>
        <StatTile
          label={`${who} ${test ? "batting second" : "chasing"}`}
          value={pct(results.chasing.win_pct)}
        >
          {results.chasing.won} of {results.chasing.matches}
          {test && ` · ${results.chasing.drawn} drawn`}
        </StatTile>
        <StatTile label="First-innings average" value={fig(results.first_innings_average, 1)}>
          {test
            ? "Runs in the match's first innings"
            : `Average total defended ${fig(results.average_total_defended, 1)}`}
        </StatTile>
      </div>
      {toss.length > 0 && (
        <div className="relative overflow-x-auto" {...scrollRegion("Toss decisions")}>
          <table className="w-full min-w-[24rem] text-sm">
            <caption className="mb-2 text-left text-sm font-medium">
              {team ? `When ${team} won the toss` : "Toss decisions"}
            </caption>
            <thead className="border-b border-border">
              <tr className="text-xs text-muted-foreground">
                <th scope="col" className="px-2 py-2 text-left font-medium">
                  Toss winner chose to
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Matches
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Toss winner won
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Win %
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {toss.map((t) => (
                <tr key={t.decision}>
                  <th scope="row" className="px-2 py-2 text-left font-sans font-normal">
                    {t.decision === "bat" ? "Bat" : "Field"}
                  </th>
                  <td className="px-2 py-2 text-right">{t.matches}</td>
                  <td className="px-2 py-2 text-right">{t.toss_winner_won}</td>
                  <td className="px-2 py-2 text-right">{pct(t.win_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
