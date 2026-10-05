import { describe, expect, it } from "vitest";

import type { SimPlayer, Timeline } from "@/lib/api/types";
import {
  move,
  oversText,
  pointsText,
  sideIssue,
  simulationRequest,
  whatIfPosition,
  type XIState,
} from "@/lib/simulator";

function player(i: number, overs = 0): SimPlayer {
  return {
    player_id: `p${i}`,
    name: `Player ${i}`,
    role: "batter",
    batting_hand: "right",
    bowling_type: null,
    position: i + 1,
    recent_overs: overs,
  };
}

const xi: XIState = {
  team: "MI",
  players: Array.from({ length: 11 }, (_, i) => player(i, i > 5 ? 40 : 0)),
  bowlers: ["p6", "p7", "p8", "p9", "p10"],
};

describe("sideIssue", () => {
  it("accepts a full XI with five bowling options", () => {
    expect(sideIssue(xi)).toBeNull();
  });

  it("asks for eleven players and five bowlers", () => {
    expect(sideIssue({ ...xi, players: xi.players.slice(0, 10) })).toMatch(/Pick 11 players/);
    expect(sideIssue({ ...xi, bowlers: ["p6", "p7"] })).toMatch(/at least 5 bowling/);
    // Bowlers who are no longer in the XI do not count.
    expect(sideIssue({ ...xi, bowlers: ["p6", "p7", "p8", "p9", "x"] })).toMatch(/at least 5/);
  });
});

describe("simulationRequest", () => {
  it("sends the batting order, the bowlers in the XI and the toss", () => {
    const request = simulationRequest(xi, { ...xi, team: "CSK" }, "toss");
    expect(request.a.batters).toEqual(xi.players.map((p) => p.player_id));
    expect(request.a.franchise_id).toBe("MI");
    expect(request.bat_first).toBeNull();
    expect(simulationRequest(xi, xi, "b").bat_first).toBe("b");
    const stale = simulationRequest({ ...xi, bowlers: [...xi.bowlers, "gone"] }, xi, "a");
    expect(stale.a.bowlers).not.toContain("gone");
  });
});

describe("helpers", () => {
  it("moves items within bounds", () => {
    expect(move(["a", "b", "c"], 0, 1)).toEqual(["b", "a", "c"]);
    expect(move(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
    expect(move(["a", "b"], 0, -1)).toEqual(["a", "b"]);
  });

  it("formats overs and point changes", () => {
    expect(oversText(57)).toBe("9.3");
    expect(oversText(120)).toBe("20.0");
    expect(pointsText(18.24)).toBe("+18.2 pts");
    expect(pointsText(-4)).toBe("−4.0 pts");
    expect(pointsText(0.01)).toBe("no change");
  });
});

function timeline(): Timeline {
  const ball = (innings_no: number, seq_no: number) => ({ innings_no, seq_no });
  return {
    innings: [
      { innings_no: 1, is_super_over: false },
      { innings_no: 2, is_super_over: false },
      { innings_no: 3, is_super_over: true },
    ],
    deliveries: [ball(1, 1), ball(1, 2), ball(2, 1), ball(2, 2), ball(3, 1), ball(3, 2)],
  } as unknown as Timeline;
}

describe("whatIfPosition", () => {
  it("starts after the current ball", () => {
    const t = timeline();
    expect(whatIfPosition(t, -1)).toEqual({ inningsNo: 1, seqNo: 0 });
    expect(whatIfPosition(t, 0)).toEqual({ inningsNo: 1, seqNo: 1 });
    expect(whatIfPosition(t, 2)).toEqual({ inningsNo: 2, seqNo: 1 });
  });

  it("moves to the start of the chase between innings", () => {
    expect(whatIfPosition(timeline(), 1)).toEqual({ inningsNo: 2, seqNo: 0 });
  });

  it("has nothing to simulate in a super over or after the last ball", () => {
    const t = timeline();
    expect(whatIfPosition(t, 3)).toBeNull();
    expect(whatIfPosition(t, 4)).toBeNull();
    expect(whatIfPosition(t, 5)).toBeNull();
  });
});
