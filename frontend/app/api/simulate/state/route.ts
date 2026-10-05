import { NextResponse, type NextRequest } from "next/server";

import { simulateState } from "@/lib/api/client";
import type { StateRequest } from "@/lib/api/types";
import { proxyError } from "@/lib/simulator-proxy";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;

/** What-if simulations for the replay, keeping the API address server-side. */
export async function POST(request: NextRequest) {
  let body: StateRequest;
  try {
    body = (await request.json()) as StateRequest;
  } catch {
    return NextResponse.json({ detail: "invalid request" }, { status: 400 });
  }
  try {
    return NextResponse.json(await simulateState(body));
  } catch (error) {
    return proxyError(error);
  }
}
