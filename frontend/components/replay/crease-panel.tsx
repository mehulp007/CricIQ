import { BallChip } from "@/components/replay/ball-chip";
import type { Timeline } from "@/lib/api/types";
import { formatRate, oversNotation } from "@/lib/cricket";
import { type BatterLine, type Frame, playerName } from "@/lib/replay/engine";
import { cn } from "@/lib/utils";

function BatterRow({
  timeline,
  line,
  onStrike,
}: {
  timeline: Timeline;
  line: BatterLine;
  onStrike: boolean;
}) {
  return (
    <tr className={cn(line.isOut && "text-muted-foreground")}>
      <th scope="row" className="py-1.5 pr-3 text-left font-normal">
        <span className={cn(onStrike && !line.isOut && "font-medium text-foreground")}>
          {playerName(timeline, line.id)}
          {onStrike && !line.isOut && <span className="text-primary"> *</span>}
        </span>
        {line.isOut && line.dismissal && (
          <span className="block text-xs text-wicket">{line.dismissal}</span>
        )}
      </th>
      <td className="py-1.5 text-right font-mono tabular-nums">
        <span className="font-semibold text-foreground">{line.runs}</span>
        <span className="text-muted-foreground"> ({line.balls})</span>
      </td>
      <td className="py-1.5 pl-3 text-right font-mono text-xs text-muted-foreground tabular-nums">
        {line.fours}×4 {line.sixes}×6
      </td>
    </tr>
  );
}

export function CreasePanel({ timeline, frame }: { timeline: Timeline; frame: Frame }) {
  const { striker, nonStriker, bowler, partnership, thisOver } = frame;
  return (
    <section aria-label="At the crease" className="rounded-2xl border border-border bg-card/70 p-5">
      <table className="w-full text-sm">
        <caption className="mb-2 text-left text-xs tracking-wide text-muted-foreground uppercase">
          Batting
        </caption>
        <tbody>
          <BatterRow timeline={timeline} line={striker} onStrike />
          <BatterRow timeline={timeline} line={nonStriker} onStrike={false} />
        </tbody>
      </table>

      <p className="mt-2 text-xs text-muted-foreground">
        Partnership{" "}
        <span className="font-mono text-foreground tabular-nums">
          {partnership.runs} ({partnership.balls})
        </span>
      </p>

      <div className="mt-5 flex items-baseline justify-between gap-3 border-t border-border pt-4 text-sm">
        <div>
          <p className="text-xs tracking-wide text-muted-foreground uppercase">Bowling</p>
          <p className="mt-1 font-medium">{playerName(timeline, bowler.id)}</p>
        </div>
        <p className="text-right font-mono tabular-nums">
          {oversNotation(bowler.legalBalls)}-{bowler.maidens}-{bowler.runs}-
          <span className="font-semibold">{bowler.wickets}</span>
          <span className="block text-xs text-muted-foreground">
            econ {formatRate(bowler.legalBalls ? (bowler.runs * 6) / bowler.legalBalls : null)}
          </span>
        </p>
      </div>

      <div className="mt-4">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">This over</p>
        <ol className="mt-2 flex flex-wrap gap-1.5" aria-label="Deliveries this over">
          {thisOver.map((d) => (
            <li key={d.seq_no}>
              <BallChip delivery={d} />
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
