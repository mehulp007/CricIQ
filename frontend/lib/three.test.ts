import { describe, expect, it } from "vitest";

import { can3D, fromBlenderPosition, fromBlenderQuaternion, verticalFov } from "@/lib/three";

const OK = { reducedMotion: false, saveData: false, webgl: true, wideEnough: true };

describe("can3D", () => {
  it("loads 3D only when nothing argues against it", () => {
    expect(can3D(OK)).toBe(true);
    expect(can3D({ ...OK, reducedMotion: true })).toBe(false);
    expect(can3D({ ...OK, saveData: true })).toBe(false);
    expect(can3D({ ...OK, webgl: false })).toBe(false);
    expect(can3D({ ...OK, wideEnough: false })).toBe(false);
  });
});

describe("Blender to three.js", () => {
  it("turns Z-up positions into Y-up", () => {
    expect(fromBlenderPosition([3.6, -6.2, 2.4])).toEqual([3.6, 2.4, 6.2]);
  });

  it("reorders and turns quaternions into Y-up", () => {
    expect(fromBlenderQuaternion([1, 0, 0, 0])).toEqual([0, 0, -0, 1]);
    // A quarter turn about Blender's up axis (Z) is a quarter turn about three.js's up axis (Y).
    const s = Math.SQRT1_2;
    expect(fromBlenderQuaternion([s, 0, 0, s])).toEqual([0, s, -0, s]);
  });

  it("matches Blender's field of view for a 36 mm sensor fitted to the width", () => {
    // 85 mm on a square frame: about 23.9 degrees either way.
    expect(verticalFov(85, 1)).toBeCloseTo(23.91, 2);
    // A wider frame keeps the horizontal angle, so the vertical one shrinks.
    expect(verticalFov(85, 1.6)).toBeLessThan(verticalFov(85, 1));
  });
});
