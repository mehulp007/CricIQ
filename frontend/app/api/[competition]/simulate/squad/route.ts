import { NextResponse, type NextRequest } from "next/server";

import { getSquad } from "@/lib/api/client";
import { isCompetitionId } from "@/lib/competitions";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

/** A side's squad in a season (?season=2010&team=CSK) for the simulator. */
export async function GET(
  request: NextRequest,
  ctx: RouteContext<"/api/[competition]/simulate/squad">,
) {
  const { competition } = await ctx.params;
  if (!isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  const params = request.nextUrl.searchParams;
  const team = params.get("team")?.toUpperCase() ?? "";
  const season = Number(params.get("season"));
  if (!/^[A-Z0-9]{2,8}$/.test(team) || !Number.isInteger(season) || season < 2000) {
    return NextResponse.json({ detail: "unknown team or season" }, { status: 400 });
  }
  try {
    return NextResponse.json(await getSquad(competition, season, team));
  } catch (error) {
    return proxyError(error);
  }
}
