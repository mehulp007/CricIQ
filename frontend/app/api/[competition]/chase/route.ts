import { NextResponse, type NextRequest } from "next/server";

import { getChase } from "@/lib/api/client";
import { isCompetitionId } from "@/lib/competitions";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

function number(value: string | null): number | undefined {
  if (value === null || value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

/** The Test chase what-if for the replay, keeping the API address server-side. */
export async function GET(request: NextRequest, ctx: RouteContext<"/api/[competition]/chase">) {
  const { competition } = await ctx.params;
  if (!isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  const query = request.nextUrl.searchParams;
  const match = number(query.get("match"));
  const seq = number(query.get("seq"));
  if (match === undefined || seq === undefined) {
    return NextResponse.json({ detail: "match and seq are required" }, { status: 400 });
  }
  try {
    return NextResponse.json(
      await getChase(competition, match, {
        seq,
        needed: number(query.get("needed")),
        wickets: number(query.get("wickets")),
        overs: number(query.get("overs")),
      }),
    );
  } catch (error) {
    return proxyError(error);
  }
}
