import { NextResponse } from "next/server";

import { wakeApi } from "@/lib/api/client";

// A sleeping API can take most of a minute to wake.
export const maxDuration = 60;
export const dynamic = "force-dynamic";

/** Wake the API before the simulator is needed (the free instance sleeps when idle). */
export async function GET() {
  const awake = await wakeApi();
  return NextResponse.json({ awake }, { status: awake ? 200 : 503 });
}
