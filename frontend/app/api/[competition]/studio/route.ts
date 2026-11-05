import { NextResponse, type NextRequest } from "next/server";

import { runStudio } from "@/lib/api/client";
import type { StudioSpec } from "@/lib/api/types";
import { isCompetitionId } from "@/lib/competitions";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

/** Runs a Chart Studio spec through the web app, keeping the API address server-side. */
export async function POST(request: NextRequest, ctx: RouteContext<"/api/[competition]/studio">) {
  const { competition } = await ctx.params;
  if (!isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  let spec: StudioSpec;
  try {
    spec = (await request.json()) as StudioSpec;
  } catch {
    return NextResponse.json({ detail: "invalid request" }, { status: 400 });
  }
  try {
    return NextResponse.json(await runStudio(competition, spec));
  } catch (error) {
    return proxyError(error);
  }
}
