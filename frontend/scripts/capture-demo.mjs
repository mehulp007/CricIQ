// Capture README screenshots and demo-GIF frames from a running CricIQ site.
//
//   node scripts/capture-demo.mjs [baseUrl]    (default: http://localhost:3000)
//
// Writes PNGs to ../docs/images/ and GIF frames to ../docs/images/frames/.
// Assemble the GIF with: uv run --with pillow python scripts/make_gif.py
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const baseUrl = process.argv[2] ?? "http://localhost:3000";
const here = path.dirname(fileURLToPath(import.meta.url));
const images = path.resolve(here, "../../docs/images");
const frames = path.join(images, "frames");

await rm(frames, { recursive: true, force: true });
await mkdir(frames, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 1,
});

await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "overview.png") });

await page.goto(`${baseUrl}/matches`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "explorer.png") });

await page.goto(`${baseUrl}/models`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "models.png") });

// Scroll so an element sits just below the sticky top bar.
async function scrollTo(locator, offset = 80) {
  await locator.evaluate((el, gap) => {
    window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - gap);
  }, offset);
}

await page.goto(`${baseUrl}/players/ba607b88`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "player.png") });

await page.goto(`${baseUrl}/matchups?batter=ba607b88&bowler=462411b3`, {
  waitUntil: "networkidle",
});
await scrollTo(page.getByRole("heading", { name: "Three ways to read the record" }));
await page.screenshot({ path: path.join(images, "matchup.png") });

// The 2019 final, from the start of the last over of the chase.
await page.goto(`${baseUrl}/matches/1181768`, { waitUntil: "networkidle" });
await page.locator("[data-replay-ready]").waitFor();
await page.getByRole("combobox", { name: "Jump to over" }).click();
await page.getByRole("option", { name: "CSK · over 19" }).click();
await page
  .getByRole("button", { name: "Pause" })
  .or(page.getByRole("button", { name: "Play" }))
  .first()
  .waitFor();
await page.mouse.click(5, 5); // move focus off the dropdown

for (let i = 0; i < 16; i++) {
  await page.screenshot({ path: path.join(frames, `${String(i).padStart(3, "0")}.png`) });
  const atEnd = await page
    .getByRole("region", { name: "Scoreboard" })
    .getByText(/won by/)
    .count();
  if (atEnd) break;
  await page.getByRole("button", { name: "Next ball" }).click();
  await page.waitForTimeout(150);
}
await page.waitForTimeout(800); // let the win probability bar settle
await page.screenshot({ path: path.join(images, "replay.png") });

await page.getByRole("tab", { name: "Scorecard" }).click();
await page.screenshot({ path: path.join(images, "scorecard.png") });

await browser.close();
console.log(`saved screenshots to ${images}`);
