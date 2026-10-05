import type { MetadataRoute } from "next";

import { FEATURED } from "@/lib/featured";
import { SITE_URL } from "@/lib/site";

const PAGES = [
  "",
  "/matches",
  "/players",
  "/matchups",
  "/compare",
  "/lab",
  "/lab/momentum",
  "/lab/pressure",
  "/lab/clutch",
  "/models",
  "/about",
];

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    ...PAGES.map((path) => ({ url: `${SITE_URL}${path}`, priority: path ? 0.8 : 1 })),
    ...FEATURED.map((m) => ({ url: `${SITE_URL}/matches/${m.match_id}`, priority: 0.6 })),
  ];
}
