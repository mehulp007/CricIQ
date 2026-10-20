import { describe, expect, it, vi } from "vitest";

import {
  cloudLayout,
  createParticles,
  drawParticles,
  fanLayout,
  GLOW_MIN_SIZE,
  hash01,
  ribbonLayout,
  seamLayout,
  sphereLayout,
  updateParticles,
} from "@/lib/canvas-particles";

/** A small seeded generator, so particle creation is reproducible in tests. */
function seeded(seed = 1) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

describe("hash01", () => {
  it("is stable and within [0, 1)", () => {
    expect(hash01(42, 3)).toBe(hash01(42, 3));
    expect(hash01(42, 3)).not.toBe(hash01(43, 3));
    for (let i = 0; i < 1000; i++) {
      const h = hash01(i, i % 7);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThan(1);
    }
  });
});

describe("createParticles", () => {
  it("scatters the requested count inside the canvas, cycling the palette", () => {
    const particles = createParticles(
      { count: 300, colors: ["red", "blue"], maxSize: 2, dampening: 0.1 },
      400,
      200,
      seeded(),
    );
    expect(particles).toHaveLength(300);
    expect(particles[0].color).toBe("red");
    expect(particles[1].color).toBe("blue");
    for (const p of particles) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(400);
      expect(p.y).toBeGreaterThanOrEqual(0);
      expect(p.y).toBeLessThanOrEqual(200);
      expect(p.size).toBeGreaterThan(0);
      expect(p.size).toBeLessThanOrEqual(2);
      expect(p.alpha).toBeGreaterThan(0);
      expect(p.alpha).toBeLessThanOrEqual(1);
    }
  });
});

describe("updateParticles", () => {
  it("moves each particle part of the way to its target", () => {
    const particles = createParticles(
      { count: 2, colors: ["red"], maxSize: 1, dampening: 0.5 },
      10,
      10,
      () => 0,
    );
    updateParticles(particles, [{ x: 10, y: 4 }], 0.5);
    expect(particles[0]).toMatchObject({ x: 5, y: 2, targetX: 10, targetY: 4 });
    // Targets repeat when there are fewer than particles.
    expect(particles[1]).toMatchObject({ x: 5, y: 2 });
    updateParticles(particles, [{ x: 10, y: 4 }], 1);
    expect(particles[0]).toMatchObject({ x: 10, y: 4 });
  });

  it("leaves particles alone without targets", () => {
    const particles = createParticles(
      { count: 1, colors: ["red"], maxSize: 1, dampening: 0.5 },
      10,
      10,
      () => 0.5,
    );
    updateParticles(particles, [], 1);
    expect(particles[0]).toMatchObject({ x: 5, y: 5 });
  });
});

describe("drawParticles", () => {
  it("draws visible particles and restores the canvas alpha", () => {
    // jsdom has no 2D canvas: the glow sprite can't be made, so particles are plain dots.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const ctx = {
      globalAlpha: 1,
      fillStyle: "",
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      drawImage: vi.fn(),
    };
    const particles = createParticles(
      { count: 3, colors: ["red"], maxSize: 2, dampening: 0.5 },
      10,
      10,
      seeded(),
    );
    particles[2].alpha = 0;
    drawParticles(ctx as unknown as CanvasRenderingContext2D, particles);
    // One particle is invisible.
    expect(ctx.fill).toHaveBeenCalledTimes(2);
    expect(ctx.drawImage).not.toHaveBeenCalled();
    expect(ctx.globalAlpha).toBe(1);
  });

  it("gives big particles a glow and fills the small ones in batches", () => {
    // A 2D context for the glow sprite, so sprites exist.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      createRadialGradient: () => ({ addColorStop: vi.fn() }),
      fillRect: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    const ctx = {
      globalAlpha: 1,
      fillStyle: "",
      beginPath: vi.fn(),
      rect: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      drawImage: vi.fn(),
    };
    const particles = createParticles(
      { count: 6, colors: ["blue"], maxSize: 1, dampening: 0.5 },
      10,
      10,
      seeded(),
    );
    particles.forEach((p, i) => {
      p.alpha = i < 4 ? 0.5 : 0.95;
      p.size = i === 0 ? GLOW_MIN_SIZE + 1 : 0.8;
    });
    drawParticles(ctx as unknown as CanvasRenderingContext2D, particles);
    expect(ctx.drawImage).toHaveBeenCalledTimes(1);
    // Five small particles at two alpha levels: two fills.
    expect(ctx.rect).toHaveBeenCalledTimes(5);
    expect(ctx.fill).toHaveBeenCalledTimes(2);
    expect(ctx.arc).not.toHaveBeenCalled();
    expect(ctx.globalAlpha).toBe(1);
  });
});

describe("layouts", () => {
  it("puts sphere points within the radius, with depth", () => {
    const points = sphereLayout(500, 100, 100, 50);
    expect(points).toHaveLength(500);
    for (const p of points) {
      expect(Math.hypot(p.x - 100, p.y - 100)).toBeLessThanOrEqual(50.0001);
      expect(p.depth).toBeGreaterThanOrEqual(0);
      expect(p.depth).toBeLessThanOrEqual(1);
    }
  });

  it("turns the sphere with its rotation", () => {
    expect(sphereLayout(10, 0, 0, 1, 0)[3]).not.toEqual(sphereLayout(10, 0, 0, 1, 1)[3]);
  });

  it("lays the seam on the ball's surface, turning with it", () => {
    const seam = seamLayout(300, 100, 100, 50, 0.4);
    expect(seam).toHaveLength(300);
    for (const p of seam) {
      expect(Math.hypot(p.x - 100, p.y - 100)).toBeLessThanOrEqual(50.0001);
    }
    expect(seamLayout(300, 100, 100, 50, 0)[10]).not.toEqual(seam[10]);
  });

  it("slides the ribbon along its line with a phase, staying on it", () => {
    const line = [
      { x: 0, y: 0 },
      { x: 100, y: 0 },
    ];
    const still = ribbonLayout(100, line, 0);
    const moved = ribbonLayout(100, line, 0, 0.25);
    expect(moved[0].x).toBeCloseTo(25);
    expect(moved[80].x).toBeCloseTo(5); // 0.8 + 0.25 wraps to 0.05
    for (const p of moved) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(100);
    }
    expect(still[99].x).toBeCloseTo(100);
  });

  it("streams the fan outwards with a phase, staying in bounds", () => {
    const points = fanLayout(500, { x: 0, y: 50 }, 100, 100, 0.6);
    for (const p of points) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(100);
    }
    expect(points[7].x).not.toBeCloseTo(fanLayout(500, { x: 0, y: 50 }, 100, 100)[7].x);
  });

  it("reuses the points it is given, frame after frame", () => {
    const out: ReturnType<typeof sphereLayout> = [];
    const first = sphereLayout(50, 0, 0, 10, 0, out);
    const kept = first[7];
    const again = sphereLayout(50, 0, 0, 10, 1, out);
    expect(again).toBe(out);
    expect(again[7]).toBe(kept);
    expect(again).toEqual(sphereLayout(50, 0, 0, 10, 1));
    const fan = fanLayout(40, { x: 0, y: 0 }, 10, 10, 0.3, []);
    expect(fanLayout(40, { x: 0, y: 0 }, 10, 10, 0.3, fan)).toEqual(
      fanLayout(40, { x: 0, y: 0 }, 10, 10, 0.3),
    );
    // A shorter layout trims the array.
    expect(sphereLayout(20, 0, 0, 10, 0, out)).toHaveLength(20);
  });

  it("covers the rectangle with the cloud", () => {
    const points = cloudLayout(1000, 300, 100);
    expect(points).toHaveLength(1000);
    expect(Math.min(...points.map((p) => p.x))).toBeLessThan(15);
    expect(Math.max(...points.map((p) => p.x))).toBeGreaterThan(285);
    for (const p of points) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(300);
      expect(p.y).toBeGreaterThanOrEqual(0);
      expect(p.y).toBeLessThanOrEqual(100);
    }
  });

  it("spreads the ribbon along the polyline within its spread", () => {
    const line = [
      { x: 0, y: 50 },
      { x: 100, y: 50 },
      { x: 200, y: 10 },
    ];
    const points = ribbonLayout(400, line, 4);
    expect(points).toHaveLength(400);
    expect(points[0].x).toBeCloseTo(0);
    expect(points[399].x).toBeCloseTo(200);
    // On the flat first segment every point is within 2.5 spreads of the line.
    for (const p of points.filter((q) => q.x <= 100)) {
      expect(Math.abs(p.y - 50)).toBeLessThanOrEqual(10.0001);
    }
    expect(ribbonLayout(5, [], 4)).toEqual([]);
  });

  it("fans strands out from the origin into a bell at the far end", () => {
    const origin = { x: 0, y: 100 };
    const points = fanLayout(3000, origin, 400, 200);
    for (const p of points) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(400);
      expect(Math.abs(p.y - 100)).toBeLessThanOrEqual(100.0001);
    }
    const far = points.filter((p) => p.x > 360);
    const middle = far.filter((p) => Math.abs(p.y - 100) < 30).length;
    const edges = far.filter((p) => Math.abs(p.y - 100) > 70).length;
    expect(middle).toBeGreaterThan(edges * 3);
  });
});
