import { NextResponse } from "next/server";

import { getNotes } from "@/lib/api/client";
import { isCompetitionId } from "@/lib/competitions";

/**
 * The latest notes for the home pages' widgets, fetched from the browser so the pages
 * stay static: ``?limit=3`` (1 to 6) and optionally ``&competition=ipl``.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const competition = url.searchParams.get("competition");
  if (competition !== null && !isCompetitionId(competition)) {
    return NextResponse.json({ detail: "unknown competition" }, { status: 404 });
  }
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit")) || 3, 1), 6);
  try {
    const list = await getNotes({ limit, competition: competition ?? undefined });
    return NextResponse.json(
      { notes: list.notes },
      { headers: { "Cache-Control": "public, max-age=300, stale-while-revalidate=3600" } },
    );
  } catch {
    return NextResponse.json({ notes: [], error: "unavailable" }, { status: 503 });
  }
}
