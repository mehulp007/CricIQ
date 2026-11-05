import { NextResponse, type NextRequest } from "next/server";

import { getMatch } from "@/lib/api/client";
import { isCompetitionId } from "@/lib/competitions";
import { proxyError } from "@/lib/simulator-proxy";

/** A match's scorecard for Chart Studio's match card. */
export async function GET(
  request: NextRequest,
  ctx: RouteContext<"/api/[competition]/studio/match">,
) {
  const { competition } = await ctx.params;
  if (!isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  const id = request.nextUrl.searchParams.get("id") ?? "";
  if (!/^\d{1,12}$/.test(id)) {
    return NextResponse.json({ detail: "invalid match" }, { status: 400 });
  }
  try {
    return NextResponse.json(await getMatch(competition, Number(id)));
  } catch (error) {
    return proxyError(error);
  }
}
