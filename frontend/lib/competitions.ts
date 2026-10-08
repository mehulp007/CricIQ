/**
 * The competitions in the switcher. Each live competition has its own pages
 * under `/[competition]/...` (`/ipl/matches`, `/odi/players/[id]`), served from
 * its own data by `/api/v2/{competition}/...`.
 */

export type CompetitionId = "ipl" | "t20i" | "odi" | "test" | "bbl" | "psl" | "cpl" | "sa20";

export type MatchFormat = "T20" | "ODI" | "Test";

/** The limited-overs competitions (everything but Tests). */
export type LimitedOversId = Exclude<CompetitionId, "test">;

export interface Competition {
  id: CompetitionId;
  /** Short label for the switcher and badges. */
  label: string;
  name: string;
  teamType: "club" | "national";
  /** Seasons that span the new year are named "2023/24". */
  spansNewYear: boolean;
  /** Whether the Analytics Lab's notes cover this competition. */
  lab: boolean;
  /** The year of its first season in the data ("2011/12" is 2012). */
  firstSeason: number;
  /** How its matches are described in prose ("every IPL match", "every men's T20I"). */
  noun: string;
  /** All of it in a sentence ("the IPL", "men's T20 internationals"). */
  collective: string;
  format: MatchFormat;
  /** Overs an innings lasts, and the most one bowler may bowl (neither limited in a Test). */
  overs: number | null;
  quota: number | null;
}

export interface UpcomingFormat {
  label: string;
  name: string;
  milestone: string;
}

export const COMPETITIONS: readonly Competition[] = [
  {
    id: "ipl",
    label: "IPL",
    name: "Indian Premier League",
    teamType: "club",
    spansNewYear: false,
    lab: true,
    firstSeason: 2008,
    noun: "IPL match",
    collective: "the IPL",
    format: "T20",
    overs: 20,
    quota: 4,
  },
  {
    id: "t20i",
    label: "T20I",
    name: "Men's T20 Internationals",
    teamType: "national",
    spansNewYear: false,
    lab: false,
    firstSeason: 2005,
    noun: "men's T20 international",
    collective: "men's T20 internationals",
    format: "T20",
    overs: 20,
    quota: 4,
  },
  {
    id: "odi",
    label: "ODI",
    name: "Men's One-Day Internationals",
    teamType: "national",
    spansNewYear: false,
    lab: false,
    firstSeason: 2002,
    noun: "men's ODI",
    collective: "men's ODIs",
    format: "ODI",
    overs: 50,
    quota: 10,
  },
  {
    id: "test",
    label: "Test",
    name: "Men's Test cricket",
    teamType: "national",
    spansNewYear: false,
    lab: false,
    firstSeason: 2001,
    noun: "men's Test",
    collective: "men's Test cricket",
    format: "Test",
    overs: null,
    quota: null,
  },
  {
    id: "bbl",
    label: "BBL",
    name: "Big Bash League",
    teamType: "club",
    spansNewYear: true,
    lab: false,
    firstSeason: 2012,
    noun: "BBL match",
    collective: "the BBL",
    format: "T20",
    overs: 20,
    quota: 4,
  },
  {
    id: "psl",
    label: "PSL",
    name: "Pakistan Super League",
    teamType: "club",
    spansNewYear: false,
    lab: false,
    firstSeason: 2016,
    noun: "PSL match",
    collective: "the PSL",
    format: "T20",
    overs: 20,
    quota: 4,
  },
  {
    id: "cpl",
    label: "CPL",
    name: "Caribbean Premier League",
    teamType: "club",
    spansNewYear: false,
    lab: false,
    firstSeason: 2013,
    noun: "CPL match",
    collective: "the CPL",
    format: "T20",
    overs: 20,
    quota: 4,
  },
  {
    id: "sa20",
    label: "SA20",
    name: "SA20",
    teamType: "club",
    spansNewYear: false,
    lab: false,
    firstSeason: 2023,
    noun: "SA20 match",
    collective: "the SA20",
    format: "T20",
    overs: 20,
    quota: 4,
  },
];

/** Formats on their way (shown in the switcher, never linked). */
export const UPCOMING: readonly UpcomingFormat[] = [];

export const DEFAULT_COMPETITION: CompetitionId = "ipl";

/** The cookie that remembers the last competition chosen. */
export const COMPETITION_COOKIE = "criciq-competition";

const BY_ID = new Map(COMPETITIONS.map((c) => [c.id, c]));

export function isCompetitionId(value: string | undefined | null): value is CompetitionId {
  return value != null && BY_ID.has(value as CompetitionId);
}

/** Whether a competition is Test cricket (four innings, draws, no over limit). */
export function isTest(id: CompetitionId): id is "test" {
  return getCompetition(id).format === "Test";
}

export function getCompetition(id: CompetitionId): Competition {
  const found = BY_ID.get(id);
  if (!found) throw new Error(`unknown competition ${id}`);
  return found;
}

/** A page of a competition: `competitionPath("t20i", "/matches")` is `/t20i/matches`. */
export function competitionPath(competition: CompetitionId, path = ""): string {
  return `/${competition}${path === "/" ? "" : path}`;
}

/** The competition a pathname belongs to (`/t20i/matches/1` -> "t20i"), if any. */
export function competitionOf(pathname: string): CompetitionId | null {
  const first = pathname.split("/")[1];
  return isCompetitionId(first) ? first : null;
}

/** The same page in another competition, where that page exists in every competition. */
export function switchPath(pathname: string, to: CompetitionId): string {
  const from = competitionOf(pathname);
  if (!from) return competitionPath(to);
  const [section, ...more] = pathname.split("/").filter(Boolean).slice(1);
  if (!section) return competitionPath(to);
  if (section === "lab" && !getCompetition(to).lab) return competitionPath(to);
  // Tests have a chase calculator where limited-overs cricket has its simulator.
  if (section === "chase" && !isTest(to)) return competitionPath(to, "/simulator");
  if (section === "simulator" && isTest(to)) return competitionPath(to, "/chase");
  // A page about one match, player or team has no counterpart in another competition.
  const sameEverywhere = more.length === 0 || (section === "teams" && more.join("/") === "h2h");
  return competitionPath(to, sameEverywhere ? `/${[section, ...more].join("/")}` : `/${section}`);
}

/** The competition in a sentence: "the BBL", or "T20Is" for internationals. */
export function phrase(competition: CompetitionId): string {
  const c = getCompetition(competition);
  return c.teamType === "national" ? `${c.label}s` : `the ${c.label}`;
}

/** Its possessive: "the BBL's", "T20Is'". */
export function possessive(competition: CompetitionId): string {
  const p = phrase(competition);
  return p.endsWith("s") ? `${p}'` : `${p}'s`;
}

/** How a season is named: "2023/24" where seasons span the new year, else the year. */
export function seasonLabel(competition: CompetitionId, year: number): string {
  if (!getCompetition(competition).spansNewYear) return String(year);
  return `${year - 1}/${String(year % 100).padStart(2, "0")}`;
}
