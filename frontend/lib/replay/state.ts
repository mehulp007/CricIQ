/**
 * Replay state machine. The cursor indexes timeline deliveries; -1 is "before
 * the first ball". Kept as a pure reducer so it is trivially testable.
 */

export type Speed = 1 | 2 | 4;

export const SPEEDS: readonly Speed[] = [1, 2, 4];

/** Milliseconds between balls at 1x. */
export const BASE_INTERVAL_MS = 1400;

export interface ReplayState {
  cursor: number;
  total: number;
  playing: boolean;
  speed: Speed;
}

export type ReplayAction =
  | { type: "play" }
  | { type: "pause" }
  | { type: "toggle" }
  | { type: "tick" }
  | { type: "next" }
  | { type: "prev" }
  | { type: "seek"; cursor: number }
  | { type: "start" }
  | { type: "end" }
  | { type: "speed"; speed: Speed };

export function initialState(total: number, cursor = -1): ReplayState {
  return { cursor: clamp(cursor, total), total, playing: false, speed: 1 };
}

function clamp(cursor: number, total: number): number {
  return Math.min(Math.max(cursor, -1), total - 1);
}

export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
  const last = state.total - 1;
  switch (action.type) {
    case "play":
      // Replaying from the end restarts the match.
      return { ...state, playing: true, cursor: state.cursor >= last ? -1 : state.cursor };
    case "pause":
      return { ...state, playing: false };
    case "toggle":
      return replayReducer(state, { type: state.playing ? "pause" : "play" });
    case "tick": {
      if (!state.playing) return state;
      const cursor = Math.min(state.cursor + 1, last);
      return { ...state, cursor, playing: cursor < last };
    }
    case "next":
      return { ...state, playing: false, cursor: clamp(state.cursor + 1, state.total) };
    case "prev":
      return { ...state, playing: false, cursor: clamp(state.cursor - 1, state.total) };
    case "seek":
      return { ...state, cursor: clamp(action.cursor, state.total) };
    case "start":
      return { ...state, playing: false, cursor: -1 };
    case "end":
      return { ...state, playing: false, cursor: last };
    case "speed":
      return { ...state, speed: action.speed };
  }
}

export function intervalFor(speed: Speed): number {
  return BASE_INTERVAL_MS / speed;
}
