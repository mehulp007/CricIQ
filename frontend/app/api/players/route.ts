import { NextResponse, type NextRequest } from "next/server";

import { getPlayers, type PlayerRoleFilter } from "@/lib/api/client";

const ROLES = new Set<PlayerRoleFilter>(["batter", "bowler", "all_rounder", "keeper"]);

/**
 * Player search for client-side pickers. Proxying through the web app keeps
 * the API address server-side and reuses its cache.
 */
export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim().slice(0, 64) ?? "";
  if (q.length < 2) return NextResponse.json({ items: [] });
  const role = request.nextUrl.searchParams.get("role") as PlayerRoleFilter | null;
  try {
    const page = await getPlayers({
      q,
      role: role && ROLES.has(role) ? role : undefined,
      pageSize: 8,
    });
    return NextResponse.json({
      items: page.items.map((p) => ({
        player_id: p.player_id,
        name: p.full_name ?? p.name,
        role: p.role,
        is_keeper: p.is_keeper,
        team: p.team?.franchise_id ?? null,
        seasons:
          p.first_season === p.last_season
            ? String(p.first_season)
            : `${p.first_season}–${p.last_season}`,
      })),
    });
  } catch {
    return NextResponse.json({ items: [], error: "unavailable" }, { status: 503 });
  }
}
