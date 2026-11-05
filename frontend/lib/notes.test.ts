import { describe, expect, it } from "vitest";

import type { Note, NoteItem, NoteSummary } from "@/lib/api/types";
import {
  addedLabel,
  articleJsonLd,
  competitionLabel,
  itemsByMatch,
  noteDateLabel,
  parseNoteSlug,
  rssFeed,
} from "@/lib/notes";

const summary = (date: string, headline: string): NoteSummary => ({
  date,
  slug: date,
  headline,
  summary: `${headline}.`,
  competitions: ["ipl", "t20i"],
  match_count: 2,
  added_on: "2026-05-31T09:30:00",
});

describe("note dates", () => {
  it("only reads real dates", () => {
    expect(parseNoteSlug("2026-05-31")).toBe("2026-05-31");
    expect(parseNoteSlug("2024-02-29")).toBe("2024-02-29");
    expect(parseNoteSlug("2023-02-29")).toBeNull();
    expect(parseNoteSlug("2026-13-01")).toBeNull();
    expect(parseNoteSlug("31-05-2026")).toBeNull();
    expect(parseNoteSlug("2026-05-31/../x")).toBeNull();
  });

  it("writes days and times as people read them", () => {
    expect(noteDateLabel("2026-05-31")).toBe("Sunday 31 May 2026");
    expect(addedLabel("2026-05-31T09:30:00")).toBe("31 May 2026");
    expect(competitionLabel("test")).toBe("Test");
    expect(competitionLabel("ipl")).toBe("IPL");
  });
});

describe("the RSS feed", () => {
  it("is well-formed XML with every note as an item", () => {
    const xml = rssFeed(
      [
        summary("2026-05-31", 'RCB beat GT <by 5 wickets> & won the "final"'),
        summary("2026-05-30", "Plain"),
      ],
      "https://criciq.example",
      "Written automatically.",
    );
    const doc = new DOMParser().parseFromString(xml, "application/xml");
    expect(doc.querySelector("parsererror")).toBeNull();
    const items = Array.from(doc.querySelectorAll("item"));
    expect(items).toHaveLength(2);
    expect(items[0].querySelector("title")?.textContent).toBe(
      'RCB beat GT <by 5 wickets> & won the "final"',
    );
    expect(items[0].querySelector("link")?.textContent).toBe(
      "https://criciq.example/notes/2026-05-31",
    );
    expect(items[0].querySelector("category")?.textContent).toBe("IPL · T20I");
    expect(items[0].querySelector("pubDate")?.textContent).toBe("Sun, 31 May 2026 23:59:00 GMT");
    expect(doc.querySelector("channel > title")?.textContent).toBe("CricIQ daily notes");
  });

  it("is still a feed with no notes", () => {
    const doc = new DOMParser().parseFromString(
      rssFeed([], "https://criciq.example", "x"),
      "application/xml",
    );
    expect(doc.querySelector("parsererror")).toBeNull();
    expect(doc.querySelectorAll("item")).toHaveLength(0);
  });
});

const item = (position: number, match_id: number): NoteItem => ({
  position,
  kind: "result",
  competition: "ipl",
  match_id,
  title: `Item ${position}`,
  body: "",
  why_it_matters: "",
  links: [],
  model: false,
});

describe("a note's items", () => {
  it("are grouped by match, in order", () => {
    const groups = itemsByMatch([item(1, 10), item(2, 10), item(3, 20), item(4, 10)]);
    expect(groups.map((g) => [g.matchId, g.items.map((i) => i.position)])).toEqual([
      [10, [1, 2]],
      [20, [3]],
      [10, [4]],
    ]);
  });

  it("describe the note for search engines", () => {
    const note = {
      ...summary("2026-05-31", "RCB won"),
      items: [],
      figures: [],
      previous: null,
      next: null,
      data_version: "v1",
      method: "x",
    } satisfies Note;
    expect(articleJsonLd(note, "https://criciq.example")).toMatchObject({
      "@type": "Article",
      headline: "RCB won",
      url: "https://criciq.example/notes/2026-05-31",
      about: ["IPL", "T20I"],
    });
  });
});
