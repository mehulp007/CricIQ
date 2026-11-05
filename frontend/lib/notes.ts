/**
 * Daily notes: slugs, labels, the RSS feed and the article markup. A note's slug is its
 * date ("2026-05-31"), the day its matches ended.
 */

import type { Note, NoteItem, NoteSummary } from "@/lib/api/types";
import { getCompetition, isCompetitionId } from "@/lib/competitions";

const SLUG = /^(\d{4})-(\d{2})-(\d{2})$/;

/** The date a slug names ("2026-05-31"), or null for anything else (or no such day). */
export function parseNoteSlug(slug: string): string | null {
  const match = SLUG.exec(slug);
  if (!match) return null;
  const [, y, m, d] = match.map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) {
    return null;
  }
  return slug;
}

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

// Spelled out here, not with toLocaleDateString, so the server and every browser agree.
function written(when: Date, weekday: boolean): string {
  const day = `${when.getUTCDate()} ${MONTHS[when.getUTCMonth()]} ${when.getUTCFullYear()}`;
  return weekday ? `${WEEKDAYS[when.getUTCDay()]} ${day}` : day;
}

/** "Sunday 31 May 2026". */
export function noteDateLabel(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return written(new Date(Date.UTC(y, m - 1, d)), true);
}

/** "31 May 2026": when a note's newest match came into the data. */
export function addedLabel(added: string): string {
  const when = new Date(added.endsWith("Z") || /[+-]\d\d:\d\d$/.test(added) ? added : `${added}Z`);
  if (Number.isNaN(when.getTime())) return added;
  return written(when, false);
}

export function notePath(date: string): string {
  return `/notes/${date}`;
}

export const KIND_LABELS: Record<NoteItem["kind"], string> = {
  result: "Result",
  turning_point: "Turning point",
  match_winner: "Match-winner",
  milestone: "Milestone",
  record: "Record",
  standings: "Standings",
};

/** A competition's short name ("IPL", "Test") from its site id. */
export function competitionLabel(id: string): string {
  return isCompetitionId(id) ? getCompetition(id).label : id.toUpperCase();
}

export function competitionsLabel(ids: string[]): string {
  return ids.map(competitionLabel).join(" · ");
}

function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** RFC 822 date of a note's day, as RSS wants it. */
function rssDate(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d, 23, 59)).toUTCString();
}

/** An RSS 2.0 feed of the given notes (newest first). */
export function rssFeed(notes: NoteSummary[], site: string, method: string): string {
  const items = notes
    .map((n) => {
      const link = `${site}${notePath(n.date)}`;
      return [
        "    <item>",
        `      <title>${escapeXml(n.headline)}</title>`,
        `      <link>${escapeXml(link)}</link>`,
        `      <guid isPermaLink="true">${escapeXml(link)}</guid>`,
        `      <pubDate>${rssDate(n.date)}</pubDate>`,
        `      <category>${escapeXml(competitionsLabel(n.competitions))}</category>`,
        `      <description>${escapeXml(n.summary)}</description>`,
        "    </item>",
      ].join("\n");
    })
    .join("\n");
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "  <channel>",
    "    <title>CricIQ daily notes</title>",
    `    <link>${escapeXml(`${site}/notes`)}</link>`,
    `    <atom:link href="${escapeXml(`${site}/notes/feed.xml`)}" rel="self" type="application/rss+xml"/>`,
    `    <description>${escapeXml(`What happened in men's cricket each day, written from the ball-by-ball data. ${method}`)}</description>`,
    "    <language>en-gb</language>",
    ...(notes[0] ? [`    <lastBuildDate>${rssDate(notes[0].date)}</lastBuildDate>`] : []),
    items,
    "  </channel>",
    "</rss>",
    "",
  ]
    .filter((line) => line !== "")
    .join("\n")
    .concat("\n");
}

/** The note as schema.org Article data for search engines. */
export function articleJsonLd(note: Note, site: string): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: note.headline,
    description: note.summary,
    datePublished: note.added_on,
    dateModified: note.added_on,
    url: `${site}${notePath(note.date)}`,
    author: { "@type": "Organization", name: "CricIQ" },
    publisher: { "@type": "Organization", name: "CricIQ" },
    about: note.competitions.map(competitionLabel),
    isBasedOn: "https://cricsheet.org",
  };
}

/** The items of a note, grouped by match in the note's order. */
export function itemsByMatch(items: NoteItem[]): { matchId: number; items: NoteItem[] }[] {
  const groups: { matchId: number; items: NoteItem[] }[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.matchId === item.match_id) last.items.push(item);
    else groups.push({ matchId: item.match_id, items: [item] });
  }
  return groups;
}
