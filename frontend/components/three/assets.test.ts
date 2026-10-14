// @vitest-environment node
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const MODELS = join(__dirname, "../../public/3d");
const glbs = readdirSync(MODELS).filter((f) => f.endsWith(".glb"));

describe("3D assets", () => {
  it("has models", () => {
    expect(glbs.length).toBeGreaterThan(0);
  });

  it.each(glbs)("%s stays within the 400 KB budget and has a poster", (file) => {
    expect(statSync(join(MODELS, file)).size).toBeLessThanOrEqual(400 * 1024);
    // One poster, or a night and a day one for a scene lit by the theme.
    const name = file.replace(/\.glb$/, "");
    const poster = (suffix: string) => existsSync(join(MODELS, "posters", `${name}${suffix}.webp`));
    expect(poster("") || (poster("-night") && poster("-day"))).toBe(true);
  });

  it.each(glbs)("%s has its Blender source", (file) => {
    const source = join(__dirname, "../../assets-src/3d", file.replace(/\.glb$/, ".blend"));
    expect(existsSync(source)).toBe(true);
  });
});
