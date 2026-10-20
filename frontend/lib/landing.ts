/**
 * The data behind the landing page, built on the server when the page is rendered: the
 * competitions for the picker, the counts in the story, and one real match's win probability.
 */
import type { PickerCard } from "@/components/competition/competition-picker";
import final2019 from "@/data/featured/ipl/1181768.json";
import type { Timeline } from "@/lib/api/types";
import { COMPETITIONS, competitionPath, seasonLabel, type Competition } from "@/lib/competitions";
import { dataVersion, featuredMatches, seasonSnapshot } from "@/lib/featured";
import { swingAt, wpAt } from "@/lib/replay/win-probability";

/**
 * Matches and deliveries per competition, counted in the warehouse for the same data version as
 * the bundled replays (the API serves match counts but not deliveries):
 *
 *   select competition_id, count(distinct match_id), count(d.match_id)
 *   from matches left join deliveries d using (match_id) group by 1
 *
 * `lib/landing.test.ts` fails when the replays are exported from newer data, so these are
 * recounted with them.
 */
export const DATA_COUNTS = {
  dataVersion: "2026-10-06.87953a3d",
  competitions: [
    { id: "test", label: "Tests", matches: 895, deliveries: 1_722_675 },
    { id: "odi", label: "ODIs", matches: 2_589, deliveries: 1_373_182 },
    { id: "t20i", label: "T20Is", matches: 3_591, deliveries: 809_306 },
    { id: "ipl", label: "IPL", matches: 1_243, deliveries: 295_732 },
    { id: "bbl", label: "BBL", matches: 662, deliveries: 153_250 },
    { id: "cpl", label: "CPL", matches: 445, deliveries: 103_717 },
    { id: "psl", label: "PSL", matches: 357, deliveries: 83_799 },
    { id: "sa20", label: "SA20", matches: 130, deliveries: 29_020 },
  ],
} as const;

export interface LandingFacts {
  dataVersion: string;
  matches: number;
  deliveries: number;
  competitions: number;
  firstSeason: number;
  perCompetition: { id: string; label: string; matches: number }[];
}

export function landingFacts(): LandingFacts {
  const rows = DATA_COUNTS.competitions;
  return {
    dataVersion: DATA_COUNTS.dataVersion,
    matches: rows.reduce((sum, r) => sum + r.matches, 0),
    deliveries: rows.reduce((sum, r) => sum + r.deliveries, 0),
    competitions: COMPETITIONS.length,
    firstSeason: Math.min(...COMPETITIONS.map((c) => c.firstSeason)),
    perCompetition: rows.map(({ id, label, matches }) => ({ id, label, matches })),
  };
}

// --------------------------------------------------------------------------- the ribbon

export interface RibbonMoment {
  label: string;
  detail: string;
  /** Where along the match (0 before the first ball, 1 after the last). */
  t: number;
  /** Team A's win probability there. */
  wp: number;
}

export interface Ribbon {
  title: string;
  href: string;
  result: string;
  teamA: { short: string; name: string };
  teamB: { short: string; name: string };
  /** Team A's win probability before the first ball and after every delivery: [t, wp]. */
  points: [number, number][];
  moments: RibbonMoment[];
}

const percent = (p: number) => `${Math.round(p * 100)}%`;

/** The 2019 IPL final from its bundled replay: Mumbai's chance of winning after every ball. */
export function probabilityRibbon(timeline: Timeline = final2019 as unknown as Timeline): Ribbon {
  const { deliveries, players, summary } = timeline;
  const name = (id: string) => players[id]?.name ?? id;
  const steps = deliveries.length;
  const points: [number, number][] = [];
  for (let cursor = -1; cursor < steps; cursor++) {
    const wp = wpAt(timeline, cursor);
    if (wp !== null) points.push([(cursor + 1) / steps, wp]);
  }
  const a = summary.team_a.franchise_id;
  const at = (cursor: number) => wpAt(timeline, cursor) ?? 0.5;
  const moments: RibbonMoment[] = [];

  // Pollard's six that did most for Mumbai.
  let six = -1;
  deliveries.forEach((d, i) => {
    if (!d.is_six || !name(d.batter_id).includes("Pollard")) return;
    if (six < 0 || (swingAt(timeline, i) ?? 0) > (swingAt(timeline, six) ?? 0)) six = i;
  });
  if (six >= 0) {
    moments.push({
      label: "Pollard's six",
      detail: `Over ${deliveries[six].ball_label} · ${a} ${percent(at(six))}`,
      t: (six + 1) / steps,
      wp: at(six),
    });
  }

  // The state before Malinga's final over of the chase.
  const lastOver = deliveries.findIndex(
    (d) => d.innings_no === 2 && d.over_no === 19 && name(d.bowler_id).includes("Malinga"),
  );
  if (lastOver > 0) {
    const before = deliveries[lastOver - 1];
    const target = timeline.innings.find((i) => i.innings_no === 2)?.target_runs ?? null;
    const need = target !== null ? target - before.team_runs : null;
    const balls = 120 - before.legal_ball_no;
    moments.push({
      label: "Malinga's final over",
      detail: `${need !== null ? `${summary.team_b.franchise_id} need ${need} off ${balls} · ` : ""}${a} ${percent(at(lastOver - 1))}`,
      t: lastOver / steps,
      wp: at(lastOver - 1),
    });
  }

  return {
    title: `IPL ${summary.season} final`,
    href: `/ipl/matches/${summary.match_id}`,
    result: summary.result_text ?? "",
    teamA: { short: a, name: summary.team_a.name },
    teamB: { short: summary.team_b.franchise_id, name: summary.team_b.name },
    points,
    moments,
  };
}

// --------------------------------------------------------------------------- the picker

function pickerCard(c: Competition): PickerCard {
  const latest = seasonSnapshot(c.id);
  return {
    id: c.id,
    href: competitionPath(c.id),
    label: c.label,
    name: c.name,
    format: c.format,
    span: `${seasonLabel(c.id, c.firstSeason)} to ${latest.label}`,
    champion: latest.champion,
    featured: featuredMatches(c.id)[0]?.headline ?? null,
  };
}

export interface PickerGroup {
  title: string;
  cards: PickerCard[];
}

export function pickerGroups(): PickerGroup[] {
  return [
    { title: "Leagues", cards: COMPETITIONS.filter((c) => c.teamType === "club").map(pickerCard) },
    {
      title: "Internationals",
      cards: COMPETITIONS.filter((c) => c.teamType === "national").map(pickerCard),
    },
  ];
}

export interface LandingData {
  facts: LandingFacts;
  ribbon: Ribbon;
  groups: PickerGroup[];
}

export function landingData(): LandingData {
  return { facts: landingFacts(), ribbon: probabilityRibbon(), groups: pickerGroups() };
}

/** For the test: the data version of the bundled replays. */
export const bundledDataVersion = () => dataVersion();
