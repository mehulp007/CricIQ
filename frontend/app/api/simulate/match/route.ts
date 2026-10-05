import { NextResponse, type NextRequest } from "next/server";

import { simulateMatch } from "@/lib/api/client";
import type { SimulationRequest } from "@/lib/api/types";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

/** Runs a simulation through the web app, keeping the API address server-side. */
export async function POST(request: NextRequest) {
  let body: SimulationRequest;
  try {
    body = (await request.json()) as SimulationRequest;
  } catch {
    return NextResponse.json({ detail: "invalid request" }, { status: 400 });
  }
  try {
    return NextResponse.json(await simulateMatch(body));
  } catch (error) {
    return proxyError(error);
  }
}
