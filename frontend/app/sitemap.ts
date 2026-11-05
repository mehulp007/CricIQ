import type { MetadataRoute } from "next";

import { COMPETITIONS, competitionPath } from "@/lib/competitions";
import { getNoteDates } from "@/lib/api/client";
import { featuredMatches } from "@/lib/featured";
import { labNotes } from "@/lib/lab";
import { allDays, dateSlug } from "@/lib/on-this-day";
import { recordKeys } from "@/lib/records";
import { SITE_URL } from "@/lib/site";

const SECTIONS = [
  "",
  "/matches",
  "/players",
  "/phases",
  "/studio",
  "/records",
  "/matchups",
  "/compare",
  "/teams",
  "/teams/h2h",
  "/simulator",
  "/models",
];

// Rebuilt daily, so each sync's new notes are listed (a build without the API lists none).
export const revalidate = 86400;

async function noteDates(): Promise<string[]> {
  try {
    return (await getNoteDates()).dates;
  } catch {
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const global = ["", "/writeup", "/about", "/on-this-day", "/notes"].map((path) => ({
    url: `${SITE_URL}${path}`,
    priority: path ? 0.8 : 1,
  }));
  const days = allDays().map((date) => ({
    url: `${SITE_URL}/on-this-day/${dateSlug(date)}`,
    priority: 0.5,
  }));
  const pages = COMPETITIONS.flatMap((c) => [
    ...SECTIONS.map((path) => ({
      url: `${SITE_URL}${competitionPath(c.id, path)}`,
      priority: path ? 0.7 : 0.9,
    })),
    ...recordKeys(c.format).map((key) => ({
      url: `${SITE_URL}${competitionPath(c.id, `/records/${key}`)}`,
      priority: 0.6,
    })),
    ...(c.teamType === "national"
      ? [{ url: `${SITE_URL}${competitionPath(c.id, "/series")}`, priority: 0.7 }]
      : []),
    ...(c.lab
      ? ["/lab", ...labNotes(c.id).map((note) => `/lab/${note.slug}`)].map((path) => ({
          url: `${SITE_URL}${competitionPath(c.id, path)}`,
          priority: 0.7,
        }))
      : []),
    ...featuredMatches(c.id).map((m) => ({
      url: `${SITE_URL}${competitionPath(c.id, `/matches/${m.match_id}`)}`,
      priority: 0.6,
    })),
  ]);
  const notes = (await noteDates()).map((date) => ({
    url: `${SITE_URL}/notes/${date}`,
    priority: 0.5,
  }));
  return [...global, ...days, ...notes, ...pages];
}
