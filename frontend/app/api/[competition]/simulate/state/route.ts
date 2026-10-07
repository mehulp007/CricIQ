import { NextResponse, type NextRequest } from "next/server";

import { simulateState } from "@/lib/api/client";
import { isCompetitionId } from "@/lib/competitions";
import type { StateRequest } from "@/lib/api/types";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

/** What-if simulations for the replay, keeping the API address server-side. */
export async function POST(
  request: NextRequest,
  ctx: RouteContext<"/api/[competition]/simulate/state">,
) {
  const { competition } = await ctx.params;
  if (!isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  let body: StateRequest;
  try {
    body = (await request.json()) as StateRequest;
  } catch {
    return NextResponse.json({ detail: "invalid request" }, { status: 400 });
  }
  try {
    return NextResponse.json(await simulateState(competition, body));
  } catch (error) {
    return proxyError(error);
  }
}
