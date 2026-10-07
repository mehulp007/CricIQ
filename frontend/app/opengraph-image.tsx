import { ImageResponse } from "next/og";

export const alt =
  "CricIQ: T20 cricket analytics with replay, win probability, players and matchups";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// A stylised win-probability worm for the card; purely decorative.
const WORM = [50, 52, 47, 55, 61, 58, 44, 40, 49, 63, 70, 66, 74, 59, 81, 90, 100];

export default function Image() {
  const step = 1040 / (WORM.length - 1);
  const points = WORM.map((v, i) => `${80 + i * step},${595 - v * 1.25}`).join(" ");
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        padding: "72px 80px",
        background: "linear-gradient(160deg, #10141c 0%, #0b1a17 100%)",
        color: "#f1f3f6",
        fontFamily: "sans-serif",
        position: "relative",
      }}
    >
      <svg
        width="1200"
        height="630"
        viewBox="0 0 1200 630"
        style={{ position: "absolute", top: 0, left: 0 }}
      >
        <polyline points={points} fill="none" stroke="#3ecf8e" strokeWidth="6" opacity="0.35" />
      </svg>
      <div style={{ display: "flex", fontSize: 34, color: "#3ecf8e", letterSpacing: 2 }}>
        CricIQ
      </div>
      <div style={{ display: "flex", flexDirection: "column", marginTop: 40 }}>
        <div style={{ fontSize: 76, fontWeight: 700, lineHeight: 1.05 }}>Decode the game.</div>
        <div style={{ fontSize: 76, fontWeight: 700, lineHeight: 1.05, color: "#8b95a7" }}>
          Predict the next move.
        </div>
      </div>
      <div style={{ display: "flex", marginTop: 44, fontSize: 30, color: "#c6ccd6" }}>
        IPL, T20Is, BBL, PSL, CPL and SA20: replay, win probability, players and matchups
      </div>
    </div>,
    size,
  );
}
