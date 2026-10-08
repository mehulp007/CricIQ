import { NextResponse, type NextRequest } from "next/server";

import { calculateChase } from "@/lib/api/client";
import { isCompetitionId } from "@/lib/competitions";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

const VENUES = new Set(["home", "away", "neutral"]);

/** The Test chase calculator, keeping the API address server-side. */
export async function GET(
  request: NextRequest,
  ctx: RouteContext<"/api/[competition]/chase-calculator">,
) {
  const { competition } = await ctx.params;
  if (!isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  const q = request.nextUrl.searchParams;
  const venue = q.get("venue") ?? "neutral";
  const numbers = ["needed", "wickets", "overs"].map((k) => Number(q.get(k)));
  const batting = q.get("batting");
  const fielding = q.get("fielding");
  if (!batting || !fielding || !VENUES.has(venue) || numbers.some((n) => !Number.isFinite(n))) {
    return NextResponse.json({ detail: "invalid chase" }, { status: 400 });
  }
  try {
    return NextResponse.json(
      await calculateChase(competition, {
        batting,
        fielding,
        venue: venue as "home" | "away" | "neutral",
        needed: numbers[0],
        wickets: numbers[1],
        overs: numbers[2],
      }),
    );
  } catch (error) {
    return proxyError(error);
  }
}
