import type { Metadata } from "next";
import Link from "next/link";

import { MatchupSelector } from "@/components/matchups/matchup-selector";
import { MatchupTable } from "@/components/matchups/matchup-table";
import { MatchupView } from "@/components/matchups/matchup-view";
import type { PickedPlayer } from "@/components/matchups/player-picker";
import { Pagination } from "@/components/matches/pagination";
import { Panel } from "@/components/players/profile-parts";
import { ApiError, type MatchupSort, getMatchup, getMatchups, getPlayer } from "@/lib/api/client";
import type { MatchupDetail, MatchupList, MatchupPhase, MatchupPlayer } from "@/lib/api/types";
import { parsePhase, parsePlayerId } from "@/lib/matchups";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Matchup Lab",
  description:
    "Batter vs bowler head-to-head records for every IPL pairing, shrunk towards what each player's overall record predicts, with next-ball odds.",
};

const PAGE_SIZE = 25;
const SORTS: { value: MatchupSort; label: string }[] = [
  { value: "balls", label: "Most balls" },
  { value: "batter_edge", label: "Batter on top" },
  { value: "bowler_edge", label: "Bowler on top" },
];

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function picked(player: MatchupPlayer): PickedPlayer {
  return { player_id: player.player_id, name: player.full_name ?? player.name };
}

async function pickedById(id: string | undefined): Promise<PickedPlayer | null> {
  if (!id) return null;
  try {
    const { player } = await getPlayer(id);
    return { player_id: player.player_id, name: player.full_name ?? player.name };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

async function loadMatchup(
  batterId: string,
  bowlerId: string,
  phase: MatchupPhase | undefined,
): Promise<MatchupDetail | null> {
  try {
    return await getMatchup(batterId, bowlerId, { phase });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

function SortLinks({ base, sort }: { base: Record<string, string>; sort: MatchupSort }) {
  return (
    <nav aria-label="Sort matchups" className="flex flex-wrap gap-1.5">
      {SORTS.map((s) => {
        const params = new URLSearchParams(base);
        if (s.value !== "balls") params.set("sort", s.value);
        const on = s.value === sort;
        return (
          <Link
            key={s.value}
            href={`/matchups?${params}`}
            aria-current={on ? "page" : undefined}
            scroll={false}
            className={cn(
              "inline-flex h-8 items-center rounded-lg border px-3 text-xs transition-colors",
              on
                ? "border-primary/50 bg-primary/10 text-foreground"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {s.label}
          </Link>
        );
      })}
    </nav>
  );
}

function ListSection({
  title,
  lede,
  list,
  show,
  base,
  sort,
  page,
}: {
  title: string;
  lede: string;
  list: MatchupList;
  show: "both" | "batter" | "bowler";
  base: Record<string, string>;
  sort: MatchupSort;
  page: number;
}) {
  const params = { ...base, ...(sort !== "balls" ? { sort } : {}) };
  return (
    <section aria-labelledby="matchup-list" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="matchup-list" className="text-lg font-semibold tracking-tight">
          {title}
        </h2>
        <p className="max-w-3xl text-sm text-muted-foreground">{lede}</p>
      </div>
      <SortLinks base={base} sort={sort} />
      {list.items.length ? (
        <MatchupTable items={list.items} show={show} />
      ) : (
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
          No matchups with enough balls.
        </p>
      )}
      <Pagination
        page={page}
        pageSize={PAGE_SIZE}
        total={list.total}
        params={params}
        basePath="/matchups"
        labels={{ previous: "Previous", next: "Next" }}
      />
    </section>
  );
}

export default async function MatchupsPage({ searchParams }: PageProps<"/matchups">) {
  const raw = await searchParams;
  const batterId = parsePlayerId(raw.batter);
  const bowlerId = parsePlayerId(raw.bowler);
  const phase = parsePhase(raw.phase);
  const sort = SORTS.find((s) => s.value === first(raw.sort))?.value ?? "balls";
  const page = Math.max(1, Number(first(raw.page)) || 1);

  let body: React.ReactNode;
  let batter: PickedPlayer | null = null;
  let bowler: PickedPlayer | null = null;

  if (batterId && bowlerId) {
    const detail = await loadMatchup(batterId, bowlerId, phase);
    if (detail) {
      batter = picked(detail.batter);
      bowler = picked(detail.bowler);
      body = <MatchupView detail={detail} />;
    } else {
      [batter, bowler] = await Promise.all([pickedById(batterId), pickedById(bowlerId)]);
      body = (
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
          One of these players could not be found.
        </p>
      );
    }
  } else if (batterId || bowlerId) {
    const asBatter = Boolean(batterId);
    const [list, who] = await Promise.all([
      getMatchups({
        batter: batterId,
        bowler: bowlerId,
        minBalls: 6,
        sort,
        page,
        pageSize: PAGE_SIZE,
      }),
      pickedById(batterId ?? bowlerId),
    ]);
    if (asBatter) batter = who;
    else bowler = who;
    const name = who?.name ?? "This player";
    body = (
      <ListSection
        title={asBatter ? `Bowlers ${name} has faced` : `Batters ${name} has bowled to`}
        lede={`Pairs with at least 6 balls. "Batter edge" is the shrunk head-to-head strike rate minus what the two players' overall records predict, so it isolates the matchup itself. Pick a ${asBatter ? "bowler" : "batter"} above or open a row for the full picture.`}
        list={list}
        show={asBatter ? "bowler" : "batter"}
        base={asBatter ? { batter: batterId! } : { bowler: bowlerId! }}
        sort={sort}
        page={page}
      />
    );
  } else {
    const list = await getMatchups({ minBalls: 60, sort, page, pageSize: PAGE_SIZE });
    body = (
      <ListSection
        title="The most-played rivalries"
        lede={`Every pair with at least 60 balls. Even the longest IPL rivalry is only around 160 balls, so head-to-head records are shrunk towards what each player's overall record predicts (the prior is worth ${Math.round(list.kappa ?? 0)} balls).`}
        list={list}
        show="both"
        base={{}}
        sort={sort}
        page={page}
      />
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Matchup Lab</h1>
        <p className="max-w-3xl text-muted-foreground">
          Batter against bowler, without over-reading a few dozen balls. Each record is read three
          ways: what happened, what the two players&apos; overall records predict, and a
          sample-size-aware estimate between them.
        </p>
      </header>
      <Panel id="pick" title="Pick a matchup">
        <MatchupSelector batter={batter} bowler={bowler} />
      </Panel>
      {body}
    </div>
  );
}
