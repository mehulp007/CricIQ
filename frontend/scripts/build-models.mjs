// Compress the 3D models exported from Blender (assets-src/3d/*.glb) into public/3d/.
//   pnpm models
// Meshopt geometry compression with quantised attributes; no simplification (it would eat the
// ball's stitching) and no joining or flattening (the stumps and bails stay separate nodes so they
// can move on their own). Fails if a model is over the 400 KB budget or has no poster.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC = "assets-src/3d";
const OUT = "public/3d";
const POSTERS = join(OUT, "posters");
const BUDGET = 400 * 1024;

mkdirSync(OUT, { recursive: true });
const models = readdirSync(SRC).filter((f) => f.endsWith(".glb"));
let failed = false;
for (const file of models) {
  const out = join(OUT, file);
  execFileSync(
    process.platform === "win32" ? "pnpm.cmd" : "pnpm",
    [
      "exec",
      "gltf-transform",
      "optimize",
      join(SRC, file),
      out,
      "--compress",
      "meshopt",
      "--texture-compress",
      "webp",
      "--simplify",
      "false",
      "--join",
      "false",
      "--flatten",
      "false",
      "--instance",
      "false",
      "--palette",
      "false",
    ],
    { stdio: "inherit", shell: process.platform === "win32" },
  );
  const size = statSync(out).size;
  const poster = join(POSTERS, file.replace(/\.glb$/, ".webp"));
  console.log(
    `${file}: ${(statSync(join(SRC, file)).size / 1024).toFixed(0)} KB -> ${(size / 1024).toFixed(0)} KB`,
  );
  if (size > BUDGET) {
    console.error(`  over the ${BUDGET / 1024} KB budget`);
    failed = true;
  }
  if (!existsSync(poster)) {
    console.error(`  no poster at ${poster}`);
    failed = true;
  }
}
process.exit(failed ? 1 : 0);
