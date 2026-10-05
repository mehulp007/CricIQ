import { NextResponse, type NextRequest } from "next/server";

import { getLatestXI, orderXI } from "@/lib/api/client";
import { proxyError } from "@/lib/simulator-proxy";

/** A franchise's latest XI (?team=MI) for the simulator's team switcher. */
export async function GET(request: NextRequest) {
  const team = request.nextUrl.searchParams.get("team")?.toUpperCase() ?? "";
  if (!/^[A-Z]{2,5}$/.test(team)) {
    return NextResponse.json({ detail: "unknown team" }, { status: 400 });
  }
  try {
    return NextResponse.json(await getLatestXI(team));
  } catch (error) {
    return proxyError(error);
  }
}

/** Any players in their usual batting order, with default bowling options. */
export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as { player_ids?: unknown };
    const ids = Array.isArray(body.player_ids) ? body.player_ids.map(String).slice(0, 11) : [];
    return NextResponse.json(await orderXI(ids));
  } catch (error) {
    return proxyError(error);
  }
}
