import { NextResponse, type NextRequest } from "next/server";

import { getSquad } from "@/lib/api/client";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

/** A side's squad in a season (?season=2010&team=CSK) for the simulator. */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const team = params.get("team")?.toUpperCase() ?? "";
  const season = Number(params.get("season"));
  if (!/^[A-Z]{2,5}$/.test(team) || !Number.isInteger(season) || season < 2008) {
    return NextResponse.json({ detail: "unknown team or season" }, { status: 400 });
  }
  try {
    return NextResponse.json(await getSquad(season, team));
  } catch (error) {
    return proxyError(error);
  }
}
