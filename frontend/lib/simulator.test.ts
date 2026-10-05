import { describe, expect, it } from "vitest";

import type { SimSeason, SimSquad, SquadPlayer, Timeline } from "@/lib/api/types";
import {
  addPlayer,
  bench,
  bowlingOvers,
  defaultTeams,
  fromSquad,
  move,
  oversText,
  pickSeason,
  pointsText,
  removePlayer,
  sideIssue,
  simulationRequest,
  whatIfPosition,
  type XIState,
} from "@/lib/simulator";

function player(i: number, overs = 0): SquadPlayer {
  return {
    player_id: `p${i}`,
    name: `Player ${i}`,
    role: "batter",
    batting_hand: "right",
    bowling_type: null,
    position: i + 1,
    recent_overs: overs,
    matches: 14 - i,
  };
}

const squadPlayers = Array.from({ length: 15 }, (_, i) => player(i, i > 5 ? 40 : 0));
const xi: XIState = {
  team: "MI",
  squad: squadPlayers,
  players: squadPlayers.slice(0, 11),
  bowlers: ["p6", "p7", "p8", "p9", "p10"],
};

describe("squads", () => {
  const squad: SimSquad = {
    team: { franchise_id: "MI", name: "Mumbai Indians", color: "#004BA0" },
    season: 2019,
    display_name: "Mumbai Indians",
    players: squadPlayers,
    xi: ["p3", "p0", "p1", "p2", "p4", "p5", "p6", "p7", "p8", "p9", "p10"],
    bowlers: ["p6", "p7", "p8", "p9", "p10"],
    from_match: 1,
    match_date: "2019-05-12",
  };

  it("starts from the season's last XI in its batting order", () => {
    const state = fromSquad(squad);
    expect(state.players.map((p) => p.player_id)).toEqual(squad.xi);
    expect(state.squad).toHaveLength(15);
    expect(bench(state).map((p) => p.player_id)).toEqual(["p11", "p12", "p13", "p14"]);
  });

  it("moves players between the bench and the XI", () => {
    const fewer = removePlayer(xi, "p6");
    expect(fewer.players).toHaveLength(10);
    expect(fewer.bowlers).not.toContain("p6");
    const back = addPlayer(fewer, "p12");
    expect(back.players.at(-1)?.player_id).toBe("p12");
    expect(back.bowlers).toContain("p12");
    expect(addPlayer(back, "p13")).toBe(back);
    expect(addPlayer(fewer, "nobody")).toBe(fewer);
  });
});

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
    const request = simulationRequest(xi, { ...xi, team: "CSK" }, "toss", 2019);
    expect(request.a.batters).toEqual(xi.players.map((p) => p.player_id));
    expect(request.a.franchise_id).toBe("MI");
    expect(request.bat_first).toBeNull();
    expect(request.season).toBe(2019);
    expect(simulationRequest(xi, xi, "b", null).bat_first).toBe("b");
    const stale = simulationRequest({ ...xi, bowlers: [...xi.bowlers, "gone"] }, xi, "a", null);
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
    expect(bowlingOvers(24)).toBe("4");
    expect(bowlingOvers(21)).toBe("3.3");
    expect(bowlingOvers(null)).toBe("—");
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

describe("seasons", () => {
  const tag = (id: string) => ({
    team: { franchise_id: id, name: id, color: "#000000" },
    display_name: id,
  });
  const seasons: SimSeason[] = [
    { season: 2026, teams: ["CSK", "GT", "MI"].map(tag) },
    { season: 2008, teams: ["DC", "KKR", "RR"].map(tag) },
  ];

  it("picks the season in the URL, or the latest", () => {
    expect(pickSeason(seasons, "2008")?.season).toBe(2008);
    expect(pickSeason(seasons, "1999")?.season).toBe(2026);
    expect(pickSeason(seasons, undefined)?.season).toBe(2026);
    expect(pickSeason([], "2008")).toBeNull();
  });

  it("keeps the asked-for sides when they played, else MI and CSK, else the first sides", () => {
    expect(defaultTeams(seasons[0], "gt", undefined)).toEqual(["GT", "MI"]);
    expect(defaultTeams(seasons[0])).toEqual(["MI", "CSK"]);
    expect(defaultTeams(seasons[0], "MI", "MI")).toEqual(["MI", "CSK"]);
    expect(defaultTeams(seasons[1], "MI", "CSK")).toEqual(["DC", "KKR"]);
  });
});
