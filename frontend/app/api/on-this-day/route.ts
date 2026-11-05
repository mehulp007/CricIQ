import { NextResponse } from "next/server";

import { getDay } from "@/lib/api/on-this-day";
import { isCompetitionId } from "@/lib/competitions";
import { parseDateSlug } from "@/lib/on-this-day";

/**
 * A day's top matches for the On This Day widgets, which ask for the visitor's own date
 * from the browser: ``?date=november-5`` and optionally ``&competition=ipl`` and
 * ``&limit=3`` (default 1).
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const date = parseDateSlug(url.searchParams.get("date") ?? "");
  if (!date) return NextResponse.json({ detail: "date must be like november-5" }, { status: 422 });
  const competition = url.searchParams.get("competition");
  if (competition !== null && !isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit")) || 1, 1), 6);
  const { entries, missing } = await getDay(date, competition ? [competition] : undefined);
  return NextResponse.json(
    { date, entries: entries.slice(0, limit), total: entries.length, missing },
    { headers: { "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400" } },
  );
}
