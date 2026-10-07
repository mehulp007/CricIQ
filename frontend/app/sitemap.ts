import type { MetadataRoute } from "next";

import { COMPETITIONS, competitionPath } from "@/lib/competitions";
import { featuredMatches } from "@/lib/featured";
import { LAB } from "@/lib/lab";
import { SITE_URL } from "@/lib/site";

const SECTIONS = [
  "",
  "/matches",
  "/players",
  "/matchups",
  "/compare",
  "/teams",
  "/teams/h2h",
  "/simulator",
  "/models",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const global = ["", "/writeup", "/about"].map((path) => ({
    url: `${SITE_URL}${path}`,
    priority: path ? 0.8 : 1,
  }));
  const pages = COMPETITIONS.flatMap((c) => [
    ...SECTIONS.map((path) => ({
      url: `${SITE_URL}${competitionPath(c.id, path)}`,
      priority: path ? 0.7 : 0.9,
    })),
    ...(c.lab
      ? ["/lab", ...LAB.map((note) => `/lab/${note.slug}`)].map((path) => ({
          url: `${SITE_URL}${competitionPath(c.id, path)}`,
          priority: 0.7,
        }))
      : []),
    ...featuredMatches(c.id).map((m) => ({
      url: `${SITE_URL}${competitionPath(c.id, `/matches/${m.match_id}`)}`,
      priority: 0.6,
    })),
  ]);
  return [...global, ...pages];
}
