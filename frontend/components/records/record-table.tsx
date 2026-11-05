import { CompetitionLink } from "@/components/competition/competition-link";
import { TeamSwatch } from "@/components/match/team-badge";
import { RankedTable, type RankedColumn } from "@/components/ui/ranked-table";
import type { RecordEntry, RecordInfo } from "@/lib/api/types";
import { matchHref, shortDate } from "@/lib/records";

function People({ entry }: { entry: RecordEntry }) {
  if (entry.players.length === 0) {
    return (
      <span className="inline-flex items-center gap-2">
        {entry.team && <TeamSwatch color={entry.team.color} />}
        {entry.team?.name ?? "—"}
      </span>
    );
  }
  const pair = entry.players.length === 2 && !entry.players.some((p) => p.role);
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
      {entry.team && <TeamSwatch color={entry.team.color} />}
      {entry.players.map((p, i) => (
        <span key={p.player_id} className="inline-flex items-center gap-1">
          {i > 0 && <span className="text-muted-foreground">{pair ? "&" : "·"}</span>}
          {/* Fifty rows of links: prefetching every one would query the API for each. */}
          <CompetitionLink
            href={`/players/${p.player_id}`}
            className="underline decoration-border underline-offset-4 hover:decoration-foreground"
            prefetch={false}
          >
            {p.name}
          </CompetitionLink>
          {p.role && (
            <span className="text-xs text-muted-foreground">
              ({p.role === "batter" ? "batting" : "bowling"})
            </span>
          )}
        </span>
      ))}
    </span>
  );
}

function Match({ entry }: { entry: RecordEntry }) {
  const href = matchHref(entry);
  const label = shortDate(entry.date) || (entry.season ? String(entry.season) : "—");
  if (!href) return <>{label}</>;
  return (
    <CompetitionLink
      href={href}
      className="underline decoration-border underline-offset-4 hover:decoration-foreground"
      aria-label={`${label}: open the match${entry.ball ? " at the ball" : ""}`}
      prefetch={false}
    >
      {label}
    </CompetitionLink>
  );
}

/** A record's entries, ranked: the figure, who, the extra figures, the opponent, ground and match. */
export function RecordTable({ record, entries }: { record: RecordInfo; entries: RecordEntry[] }) {
  const perMatch = record.level !== "career";
  const columns: RankedColumn<RecordEntry>[] = [
    {
      key: "who",
      header: record.level === "stand" ? "Batters" : record.group === "teams" ? "Side" : "Player",
      cell: (e) => <People entry={e} />,
    },
    {
      key: "value",
      header: record.unit ? record.unit[0].toUpperCase() + record.unit.slice(1) : "Figure",
      cell: (e) => <span className="font-semibold">{e.display}</span>,
      numeric: true,
    },
    ...record.columns.map((label, i): RankedColumn<RecordEntry> => ({
      key: `figure-${i}`,
      header: label,
      cell: (e) => e.figures[i]?.value ?? "—",
      numeric: true,
      wide: i > 1,
    })),
  ];
  if (record.level === "season") {
    columns.push({ key: "season", header: "Season", cell: (e) => e.season ?? "—", numeric: true });
  }
  if (perMatch && record.level !== "season") {
    columns.push(
      {
        key: "opponent",
        header: "Against",
        cell: (e) => e.opponent?.name ?? "—",
        wide: true,
      },
      { key: "venue", header: "Ground", cell: (e) => e.venue ?? "—", wide: true },
      { key: "date", header: "Match", cell: (e) => <Match entry={e} /> },
    );
  }
  return (
    <RankedTable
      label={record.label}
      rows={entries}
      columns={columns}
      rowKey={(e) =>
        `${e.rank}-${e.players.map((p) => p.player_id).join("-")}-${e.team?.franchise_id ?? ""}-${e.match_id ?? ""}-${e.season ?? ""}-${e.ball ?? ""}`
      }
    />
  );
}
