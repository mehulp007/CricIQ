import { NextResponse } from "next/server";

import { getRecords, getTeams } from "@/lib/api/client";
import { isCompetitionId, seasonLabel } from "@/lib/competitions";
import { featuredMatches } from "@/lib/featured";
import { GROUP_LABELS } from "@/lib/records";

/**
 * What the search palette lists for a competition besides players (which it searches as you
 * type): every team, every record list and the featured replays. Small, fetched once when
 * the palette opens.
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
  // Featured replays are bundled, so they are offered even while the API is unavailable.
  const [overview, hub] = await Promise.all([
    getTeams(competition).catch(() => null),
    getRecords(competition).catch(() => null),
  ]);
  const teams = (overview?.franchises ?? []).map((t) => ({
    id: t.franchise_id,
    name: t.name,
    color: t.color,
    active: t.is_active,
  }));
  const records = (hub?.records ?? []).map(({ record }) => ({
    key: record.key,
    label: record.label,
    group: GROUP_LABELS[record.group],
  }));
  return NextResponse.json({ teams, records, matches });
}
