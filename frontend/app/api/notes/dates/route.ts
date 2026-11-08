import { NextResponse } from "next/server";

import { getNoteDates } from "@/lib/api/client";

/** Every day with a daily note, for the search palette (which looks a date up in them). */
export async function GET() {
  try {
    return NextResponse.json(await getNoteDates(), {
      headers: { "Cache-Control": "public, max-age=300, stale-while-revalidate=3600" },
    });
  } catch {
    return NextResponse.json({ dates: [] }, { status: 503 });
  }
}
