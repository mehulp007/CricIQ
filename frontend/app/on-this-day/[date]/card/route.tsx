import { ImageResponse } from "next/og";

import { getDay } from "@/lib/api/on-this-day";
import { dayLabel, parseDateSlug } from "@/lib/on-this-day";

const SIZE = { width: 1200, height: 630 };

/** A shareable card for a day: its most notable match, its figure and result. */
export async function GET(_request: Request, ctx: RouteContext<"/on-this-day/[date]/card">) {
  const date = parseDateSlug((await ctx.params).date);
  if (!date) return new Response("not a date", { status: 404 });
  const { entries } = await getDay(date);
  const top = entries[0];
  const label = dayLabel(date);
  const more = entries.length - 1;

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        padding: "64px 80px",
        background: "linear-gradient(160deg, #10141c 0%, #0b1a17 100%)",
        color: "#f1f3f6",
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30 }}>
        <span style={{ color: "#3ecf8e", letterSpacing: 2 }}>CricIQ</span>
        <span style={{ color: "#8b95a7" }}>On this day · {label}</span>
      </div>
      {top ? (
        <div style={{ display: "flex", flexDirection: "column", marginTop: 56, flexGrow: 1 }}>
          <div style={{ display: "flex", fontSize: 28, color: "#8b95a7" }}>
            {`${top.year} · ${top.label}${top.stage && top.stage !== "League" ? ` · ${top.stage}` : ""}`}
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 40, marginTop: 18 }}>
            {top.highlight && (
              <div style={{ display: "flex", fontSize: 150, fontWeight: 700, lineHeight: 1 }}>
                {top.highlight.figure}
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", flexShrink: 1 }}>
              <div style={{ display: "flex", fontSize: 46, fontWeight: 700 }}>
                {top.highlight ? top.highlight.name : top.headline}
              </div>
              {top.highlight && (
                <div style={{ display: "flex", fontSize: 30, color: "#c6ccd6", marginTop: 6 }}>
                  {`${top.highlight.detail}${top.highlight.against ? ` against ${top.highlight.against}` : ""}`}
                </div>
              )}
            </div>
          </div>
          <div style={{ display: "flex", fontSize: 32, color: "#c6ccd6", marginTop: 36 }}>
            {`${top.teams.map((t) => t.name).join(" v ")} · ${top.result}`}
          </div>
          <div style={{ display: "flex", flexGrow: 1 }} />
          <div style={{ display: "flex", fontSize: 26, color: "#8b95a7" }}>
            {more > 0
              ? `and ${more} more ${more === 1 ? "match" : "matches"} on ${label} · Data: Cricsheet`
              : "Data: Cricsheet"}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", fontSize: 54, fontWeight: 700, marginTop: 120 }}>
          {`No matches in CricIQ's data on ${label}.`}
        </div>
      )}
    </div>,
    SIZE,
  );
}
