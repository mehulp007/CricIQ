import { describe, expect, it } from "vitest";

import { initialState, intervalFor, replayReducer, type ReplayState } from "./state";

const at = (cursor: number, extra: Partial<ReplayState> = {}): ReplayState => ({
  ...initialState(10, cursor),
  ...extra,
});

describe("replayReducer", () => {
  it("starts before the first ball, paused", () => {
    expect(initialState(10)).toEqual({ cursor: -1, total: 10, playing: false, speed: 1 });
  });

  it("advances on tick only while playing", () => {
    expect(replayReducer(at(3), { type: "tick" }).cursor).toBe(3);
    expect(replayReducer(at(3, { playing: true }), { type: "tick" }).cursor).toBe(4);
  });

  it("stops at the last ball", () => {
    const end = replayReducer(at(8, { playing: true }), { type: "tick" });
    expect(end).toMatchObject({ cursor: 9, playing: false });
    expect(replayReducer(end, { type: "tick" }).cursor).toBe(9);
  });

  it("restarts when played from the end", () => {
    expect(replayReducer(at(9), { type: "play" })).toMatchObject({ cursor: -1, playing: true });
  });

  it("steps and seeks within bounds, pausing on manual steps", () => {
    expect(replayReducer(at(0, { playing: true }), { type: "prev" })).toMatchObject({
      cursor: -1,
      playing: false,
    });
    expect(replayReducer(at(-1), { type: "prev" }).cursor).toBe(-1);
    expect(replayReducer(at(9), { type: "next" }).cursor).toBe(9);
    expect(replayReducer(at(0), { type: "seek", cursor: 42 }).cursor).toBe(9);
    expect(replayReducer(at(5), { type: "start" }).cursor).toBe(-1);
    expect(replayReducer(at(5), { type: "end" }).cursor).toBe(9);
  });

  it("toggles play and changes speed", () => {
    expect(replayReducer(at(2), { type: "toggle" }).playing).toBe(true);
    expect(replayReducer(at(2, { playing: true }), { type: "toggle" }).playing).toBe(false);
    expect(replayReducer(at(2), { type: "speed", speed: 4 }).speed).toBe(4);
    expect(intervalFor(4)).toBe(intervalFor(1) / 4);
  });
});
