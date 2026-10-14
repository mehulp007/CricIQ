import { describe, expect, it } from "vitest";

import { filterResults, groupResults, matchScore, type SearchResult } from "@/lib/search";

const r = (id: string, group: SearchResult["group"], label: string, detail?: string) => ({
  id,
  group,
  label,
  detail,
  href: `/${id}`,
});

describe("matchScore", () => {
  it("matches the start of any word, every query word", () => {
    expect(matchScore("kol kn", "Kolkata Knight Riders")).not.toBeNull();
    expect(matchScore("knight", "Kolkata Knight Riders")).not.toBeNull();
    expect(matchScore("night", "Kolkata Knight Riders")).toBeNull();
    expect(matchScore("kolkata delhi", "Kolkata Knight Riders")).toBeNull();
  });

  it("ignores case and accents", () => {
    expect(matchScore("MULLER", "Müller")).not.toBeNull();
  });

  it("ranks a match at the very start highest", () => {
    expect(matchScore("ma", "Matches")!).toBeGreaterThan(
      matchScore("ma", "Model Insights about matches")!,
    );
  });
});

describe("filterResults and groupResults", () => {
  const all = [
    r("a", "Pages", "Players"),
    r("b", "Pages", "Matches"),
    r("c", "Competitions", "IPL", "Indian Premier League"),
    r("d", "Teams", "Mumbai Indians", "MI"),
  ];

  it("keeps everything, in order, for an empty query", () => {
    expect(filterResults("  ", all).map((x) => x.id)).toEqual(["a", "b", "c", "d"]);
  });

  it("matches the detail too", () => {
    expect(filterResults("indian", all).map((x) => x.id)).toEqual(["c", "d"]);
  });

  it("groups in a fixed order and caps each group", () => {
    const many = Array.from({ length: 9 }, (_, i) => r(`p${i}`, "Players", `Player ${i}`));
    const grouped = groupResults([...many, all[0]], 6);
    expect(grouped.map((g) => g.group)).toEqual(["Pages", "Players"]);
    expect(grouped[1].items).toHaveLength(6);
  });
});
