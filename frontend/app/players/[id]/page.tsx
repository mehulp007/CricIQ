import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BattingView, BowlingView, PlayerHeader } from "@/components/players/player-profile";
import { SeasonWindow } from "@/components/players/season-window";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ApiError,
  getMatchups,
  getPlayer,
  getPlayerSplits,
  type SeasonWindow as Window,
} from "@/lib/api/client";
import type { PlayerProfile } from "@/lib/api/types";
import { parseSeason, rate, roleLabel } from "@/lib/players";

function windowFrom(raw: Record<string, string | string[] | undefined>): Window {
  const from = parseSeason(raw.from);
  const to = parseSeason(raw.to);
  return from && to && from > to ? { from: to, to: from } : { from, to };
}

async function loadProfile(id: string, window: Window): Promise<PlayerProfile> {
  if (!/^[\w-]{1,32}$/.test(id)) notFound();
  try {
    return await getPlayer(id, window);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({ params }: PageProps<"/players/[id]">): Promise<Metadata> {
  const { id } = await params;
  try {
    const { player, batting, bowling } = await loadProfile(id, {});
    const name = player.full_name ?? player.name;
    const lines = [
      batting &&
        batting.runs > 0 &&
        `${batting.runs} runs at a strike rate of ${rate(batting.strike_rate, 1)}`,
      bowling &&
        bowling.wickets > 0 &&
        `${bowling.wickets} wickets at an economy of ${rate(bowling.economy)}`,
    ].filter(Boolean);
    return {
      title: `${name}: IPL profile`,
      description: `${name}, ${roleLabel(player.role, player.is_keeper).toLowerCase()}, ${player.matches} IPL matches ${player.first_season}–${player.last_season}. ${lines.join("; ")}. Splits by phase, venue and opposition, measured against par.`,
    };
  } catch {
    return { title: "Player profile" };
  }
}

export default async function PlayerPage({ params, searchParams }: PageProps<"/players/[id]">) {
  const { id } = await params;
  const window = windowFrom(await searchParams);
  // Matchups are an extra: the profile still renders if they are unavailable.
  const opponents = (side: "batter" | "bowler") =>
    getMatchups({ [side]: id, ...window, minBalls: 12, pageSize: 6 }).catch(() => null);
  const [profile, splits, bowlersFaced, battersFaced] = await Promise.all([
    loadProfile(id, window),
    getPlayerSplits(id, window).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 404) notFound();
      throw error;
    }),
    opponents("batter"),
    opponents("bowler"),
  ]);
  const { player } = profile;
  const first = Math.max(profile.window.first, player.first_season);
  const last = Math.min(profile.window.last, player.last_season);
  const hasBatting = profile.batting !== null && profile.batting !== undefined;
  const hasBowling =
    profile.bowling !== null && profile.bowling !== undefined && profile.bowling.balls > 0;
  const primary =
    player.role === "bowler" && hasBowling ? "bowling" : hasBatting ? "batting" : "bowling";

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <Link href="/players" className="hover:text-foreground">
          Players
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="text-foreground">{player.full_name ?? player.name}</span>
      </nav>

      <PlayerHeader profile={profile} />

      <SeasonWindow career={[player.first_season, player.last_season]} first={first} last={last} />

      {hasBatting || hasBowling ? (
        <Tabs key={`${first}-${last}`} defaultValue={primary}>
          <TabsList>
            {hasBatting && <TabsTrigger value="batting">Batting</TabsTrigger>}
            {hasBowling && <TabsTrigger value="bowling">Bowling</TabsTrigger>}
          </TabsList>
          {hasBatting && (
            <TabsContent value="batting" className="mt-6">
              <BattingView profile={profile} splits={splits} matchups={bowlersFaced} />
            </TabsContent>
          )}
          {hasBowling && (
            <TabsContent value="bowling" className="mt-6">
              <BowlingView profile={profile} splits={splits} matchups={battersFaced} />
            </TabsContent>
          )}
        </Tabs>
      ) : (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-muted-foreground">
          {player.full_name ?? player.name} played in these seasons without batting or bowling.
        </p>
      )}
    </div>
  );
}
