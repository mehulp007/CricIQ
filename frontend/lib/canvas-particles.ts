/**
 * A lightweight 2D particle system using the native Canvas API.
 * No WebGL required. Renders up to ~5000 particles at 60fps on modern devices.
 *
 * Used by the landing page to represent the millions of deliveries in the data as a
 * flowing point cloud that morphs between shapes as the visitor scrolls.
 *
 * The layouts are pure functions of their inputs (no Math.random), so a shape
 * is the same on every frame and every visit, and is unit-tested.
 */

export interface Particle {
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  size: number;
  alpha: number;
  color: string;
}

export interface ParticleSystemConfig {
  count: number;
  colors: string[];
  maxSize: number;
  dampening: number; // 0–1, how quickly particles reach their target
}

/** A layout position. `depth` (0 at the back, 1 at the front) is set by layouts with depth. */
export interface LayoutPoint {
  x: number;
  y: number;
  depth?: number;
}

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/** A stable pseudo-random number in [0, 1) for an index and a salt (an integer hash). */
export function hash01(index: number, salt = 0): number {
  let h = Math.imul(index ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(salt + 1, 0xc2b2ae35);
  h = Math.imul(h ^ (h >>> 16), 0x7feb352d);
  h = Math.imul(h ^ (h >>> 15), 0x846ca68b);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

/** A stable standard-normal number for an index (Box–Muller over two hashes). */
function normal(index: number, salt: number): number {
  const u = Math.max(hash01(index, salt), 1e-9);
  const v = hash01(index, salt + 101);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export function createParticles(
  config: ParticleSystemConfig,
  width: number,
  height: number,
  random: () => number = Math.random,
): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < config.count; i++) {
    const x = random() * width;
    const y = random() * height;
    particles.push({
      x,
      y,
      targetX: x,
      targetY: y,
      // Mostly small points with a few larger ones, so the cloud has texture.
      size: config.maxSize * (0.35 + 0.65 * random() ** 3),
      alpha: 0.35 + 0.65 * random(),
      color: config.colors[i % config.colors.length] ?? "#ffffff",
    });
  }
  return particles;
}

export function updateParticles(
  particles: Particle[],
  targets: { x: number; y: number }[],
  dampening: number,
): void {
  if (targets.length === 0) return;
  const t = Math.min(Math.max(dampening, 0), 1);
  for (let i = 0; i < particles.length; i++) {
    const p = particles[i];
    const target = targets[i % targets.length];
    p.targetX = target.x;
    p.targetY = target.y;
    p.x += (target.x - p.x) * t;
    p.y += (target.y - p.y) * t;
  }
}

// One soft glow sprite per colour and size bucket, drawn with drawImage: far cheaper per particle
// than shadowBlur or a radial gradient each frame.
const SPRITE_SIZE = 32;
const sprites = new Map<string, HTMLCanvasElement | null>();

function glowSprite(color: string): HTMLCanvasElement | null {
  if (sprites.has(color)) return sprites.get(color) ?? null;
  let sprite: HTMLCanvasElement | null = null;
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = SPRITE_SIZE;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      const r = SPRITE_SIZE / 2;
      const gradient = ctx.createRadialGradient(r, r, 0, r, r, r);
      gradient.addColorStop(0, color);
      gradient.addColorStop(0.25, color);
      gradient.addColorStop(1, "transparent");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, SPRITE_SIZE, SPRITE_SIZE);
      sprite = canvas;
    }
  }
  sprites.set(color, sprite);
  return sprite;
}

/** Below this size (CSS px) a particle's glow can't be seen: it is drawn as a plain square. */
export const GLOW_MIN_SIZE = 1.25;
const ALPHA_LEVELS = 12;
// The small particles of each colour and alpha level, gathered every frame into lists kept between
// frames (no new arrays per frame).
const batches = new Map<string, number[][]>();

/**
 * Draw the particles. Those big enough to show a glow get the colour's glow sprite; the many small
 * ones are squares of the same area, gathered by colour and (rounded) alpha so each group is one
 * path and one fill. With additive blending ("lighter") the order doesn't change the picture, and
 * thousands of image draws a frame become a few dozen fills.
 */
export function drawParticles(ctx: CanvasRenderingContext2D, particles: Particle[]): void {
  const previousAlpha = ctx.globalAlpha;
  for (const lists of batches.values()) for (const list of lists) list.length = 0;

  for (let i = 0; i < particles.length; i++) {
    const p = particles[i];
    if (p.alpha <= 0.01 || p.size <= 0) continue;
    const sprite = glowSprite(p.color);
    if (!sprite) {
      ctx.globalAlpha = Math.min(p.alpha, 1);
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
    } else if (p.size >= GLOW_MIN_SIZE) {
      ctx.globalAlpha = Math.min(p.alpha, 1);
      // The sprite's bright core is about half its width: scale it so the core matches the size.
      const r = p.size * 2;
      ctx.drawImage(sprite, p.x - r, p.y - r, r * 2, r * 2);
    } else {
      let lists = batches.get(p.color);
      if (!lists) {
        lists = Array.from({ length: ALPHA_LEVELS }, () => []);
        batches.set(p.color, lists);
      }
      const level = Math.min(ALPHA_LEVELS - 1, Math.floor(Math.min(p.alpha, 1) * ALPHA_LEVELS));
      lists[level].push(i);
    }
  }

  for (const [color, lists] of batches) {
    ctx.fillStyle = color;
    for (let level = 0; level < ALPHA_LEVELS; level++) {
      const list = lists[level];
      if (list.length === 0) continue;
      ctx.globalAlpha = (level + 0.5) / ALPHA_LEVELS;
      ctx.beginPath();
      for (const i of list) {
        const p = particles[i];
        // A square with the area of a disc of the particle's size.
        const side = p.size * 1.77;
        ctx.rect(p.x - side / 2, p.y - side / 2, side, side);
      }
      ctx.fill();
    }
  }
  ctx.globalAlpha = previousAlpha;
}

const TILT = 0.35;

/**
 * Project a point on the unit sphere: turn it by `rotation` about the vertical axis, tilt the top
 * towards the viewer, and drop the depth axis (orthographic).
 */
function project(
  target: LayoutPoint,
  x: number,
  y: number,
  z: number,
  rotation: number,
  cx: number,
  cy: number,
  radius: number,
): void {
  const rx = x * Math.cos(rotation) - z * Math.sin(rotation);
  const rz = x * Math.sin(rotation) + z * Math.cos(rotation);
  const ty = y * Math.cos(TILT) - rz * Math.sin(TILT);
  const tz = y * Math.sin(TILT) + rz * Math.cos(TILT);
  target.x = cx + rx * radius;
  target.y = cy + ty * radius;
  target.depth = (tz + 1) / 2;
}

/**
 * The point to write at `i`: the one already in `out` (layouts called every frame pass the same
 * array back, so no new objects are made) or a new one.
 */
function slot(out: LayoutPoint[], i: number): LayoutPoint {
  return (out[i] ??= { x: 0, y: 0 });
}

/** Finish a layout written into `out`: trim it to `count` points. */
function fill(out: LayoutPoint[], count: number): LayoutPoint[] {
  out.length = count;
  return out;
}

// Each particle's normally distributed offset never changes: work it out once per salt.
const normals = new Map<number, Float32Array>();
function cachedNormal(i: number, salt: number): number {
  let table = normals.get(salt);
  if (!table || table.length <= i) {
    const grown = new Float32Array(Math.max(i + 1, (table?.length ?? 0) * 2, 1024));
    for (let k = 0; k < grown.length; k++) grown[k] = normal(k, salt);
    normals.set(salt, grown);
    table = grown;
  }
  return table[i];
}

/**
 * Arrange particles into a sphere-like projection (2D illusion of 3D).
 * Used in Chapter 1 (the cricket ball silhouette).
 *
 * Points lie on a Fibonacci sphere turned by `rotation` (radians about the vertical axis) and
 * tilted towards the viewer, projected orthographically; `depth` says how near each point is.
 */
export function sphereLayout(
  count: number,
  cx: number,
  cy: number,
  radius: number,
  rotation = 0,
  out: LayoutPoint[] = [],
): LayoutPoint[] {
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 0 : 1 - (i / (count - 1)) * 2;
    const ring = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN_ANGLE * i;
    project(
      slot(out, i),
      Math.cos(theta) * ring,
      y,
      Math.sin(theta) * ring,
      rotation,
      cx,
      cy,
      radius,
    );
  }
  return fill(out, count);
}

/**
 * The ball's seam on the same sphere (Chapter 1): a great circle, with a row of stitches either
 * side of it, turning with the ball. Every third point is on the seam itself, the rest alternate
 * between the two stitch rows.
 */
export function seamLayout(
  count: number,
  cx: number,
  cy: number,
  radius: number,
  rotation = 0,
  out: LayoutPoint[] = [],
): LayoutPoint[] {
  // The seam's plane is nearly upright, so the seam sweeps across the ball as it turns.
  const n = [0.94, 0.34, 0];
  const e1 = [-0.34, 0.94, 0];
  const e2 = [0, 0, 1];
  for (let i = 0; i < count; i++) {
    const u = (i / Math.max(count, 1)) * Math.PI * 2;
    const row = i % 3 === 0 ? 0 : i % 3 === 1 ? 1 : -1;
    const lift = row * 0.045;
    const scale = Math.sqrt(1 - lift * lift);
    const c = Math.cos(u) * scale;
    const s = Math.sin(u) * scale;
    project(
      slot(out, i),
      c * e1[0] + s * e2[0] + lift * n[0],
      c * e1[1] + s * e2[1] + lift * n[1],
      c * e1[2] + s * e2[2] + lift * n[2],
      rotation,
      cx,
      cy,
      radius,
    );
  }
  return fill(out, count);
}

/**
 * Arrange particles in a vast, even point cloud over a rectangle (Chapter 2). Stratified on a
 * jittered grid, so it reads as "everything" rather than as random clumps.
 */
export function cloudLayout(count: number, width: number, height: number): LayoutPoint[] {
  const cols = Math.max(1, Math.round(Math.sqrt((count * width) / Math.max(height, 1))));
  const rows = Math.max(1, Math.ceil(count / cols));
  const points: LayoutPoint[] = [];
  for (let i = 0; i < count; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    points.push({
      x: ((col + hash01(i, 7)) / cols) * width,
      y: ((row + hash01(i, 13)) / rows) * height,
      depth: hash01(i, 19),
    });
  }
  return points;
}

/**
 * Arrange particles into a flowing ribbon (the win-probability curve).
 * Used in Chapter 3.
 *
 * Particles are spaced evenly along the polyline by arc length, each pushed off the line by a
 * stable, normally distributed amount scaled by `spread` (so the ribbon is dense at its centre).
 * A `phase` (0–1) slides every particle along the line, wrapping at the end, so the ribbon flows.
 */
export function ribbonLayout(
  count: number,
  points: { x: number; y: number }[],
  spread: number,
  phase = 0,
  out: LayoutPoint[] = [],
): LayoutPoint[] {
  if (points.length === 0) return fill(out, 0);
  if (points.length === 1) {
    for (let i = 0; i < count; i++) Object.assign(slot(out, i), points[0], { depth: undefined });
    return fill(out, count);
  }
  const lengths = [0];
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    lengths.push(lengths[i - 1] + Math.hypot(dx, dy));
  }
  const total = lengths[lengths.length - 1];
  for (let i = 0; i < count; i++) {
    const fraction = phase
      ? (((i / count + phase) % 1) + 1) % 1
      : count === 1
        ? 0
        : i / (count - 1);
    const distance = fraction * total;
    // The first segment whose end is at or past the distance.
    let lo = 1;
    let hi = points.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (lengths[mid] < distance) lo = mid + 1;
      else hi = mid;
    }
    const segment = lo;
    const span = lengths[segment] - lengths[segment - 1] || 1;
    const t = (distance - lengths[segment - 1]) / span;
    const a = points[segment - 1];
    const b = points[segment];
    const offset = Math.max(-2.5, Math.min(2.5, cachedNormal(i, 3))) * spread;
    const p = slot(out, i);
    p.x = a.x + (b.x - a.x) * t;
    p.y = a.y + (b.y - a.y) * t + offset;
    p.depth = 1 - Math.min(Math.abs(offset) / (spread * 2.5 || 1), 1);
  }
  return fill(out, count);
}

/**
 * Arrange particles into a fan/explosion of simulation strands.
 * Used in Chapter 4.
 *
 * Each particle sits on a strand leaving `origin` and running `width` to the right; strands end at
 * normally distributed heights within `height`, so the far end is dense in the middle like a
 * bell curve. Points cluster towards the far end, where the outcomes are. A `phase` (0–1) moves
 * every particle outwards along its strand, wrapping back to the origin, so the strands stream.
 */
export function fanLayout(
  count: number,
  origin: { x: number; y: number },
  width: number,
  height: number,
  phase = 0,
  out: LayoutPoint[] = [],
): LayoutPoint[] {
  for (let i = 0; i < count; i++) {
    const end = Math.max(-2.6, Math.min(2.6, cachedNormal(i, 5))) / 2.6; // -1 … 1
    const t = Math.sqrt((((hash01(i, 11) + phase) % 1) + 1) % 1); // more points further along
    // Strands leave the origin flat and open out (an ease-in on the vertical).
    const rise = t * t;
    const p = slot(out, i);
    p.x = origin.x + width * t;
    p.y = origin.y + end * (height / 2) * rise;
    p.depth = t;
  }
  return fill(out, count);
}
