import { connection } from "next/server";

import { getNotes } from "@/lib/api/client";
import { rssFeed } from "@/lib/notes";
import { SITE_URL } from "@/lib/site";

const ITEMS = 30;

/** The latest daily notes as an RSS 2.0 feed. */
export async function GET() {
  await connection();
  try {
    const list = await getNotes({ limit: ITEMS });
    return new Response(rssFeed(list.notes, SITE_URL, list.method), {
      headers: {
        "Content-Type": "application/rss+xml; charset=utf-8",
        "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
      },
    });
  } catch {
    return new Response("The notes are unavailable just now.", { status: 503 });
  }
}
