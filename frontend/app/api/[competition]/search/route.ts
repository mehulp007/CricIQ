import { NextResponse } from "next/server";

import { getTeams } from "@/lib/api/client";
import { isCompetitionId, seasonLabel } from "@/lib/competitions";
import { featuredMatches } from "@/lib/featured";

/**
 * What the search palette lists for a competition besides players (which it searches as you
 * type): every team and the featured replays. Small, fetched once when the palette opens.
 */
export async function GET(_request: Request, ctx: RouteContext<"/api/[competition]/search">) {
  const { competition } = await ctx.params;
  if (!isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  const matches = featuredMatches(competition).map((m) => ({
    match_id: m.match_id,
    headline: m.headline,
    detail: `${m.summary.team_a.name} v ${m.summary.team_b.name} · ${seasonLabel(competition, m.summary.season)}`,
  }));
  try {
    const overview = await getTeams(competition);
    const teams = overview.franchises.map((t) => ({
      id: t.franchise_id,
      name: t.name,
      color: t.color,
      active: t.is_active,
    }));
    return NextResponse.json({ teams, matches });
  } catch {
    // Featured replays are bundled, so they are offered even while the API is unavailable.
    return NextResponse.json({ teams: [], matches });
  }
}
