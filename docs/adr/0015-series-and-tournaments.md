# ADR-0015: Series and tournaments from Cricsheet's event names

- **Status:** Accepted
- **Date:** 2026-10-08

## Context

V2-7 gives international cricket the structure fans follow it by: series ("England won 2–1"),
major tournaments with their tables and knockouts, two sides' record in every format, a player's
career across formats, and Analytics Lab notes that compare formats.

Cricsheet has no series or tournament records. Each match carries its event: a name ("The
Ashes", "India tour of Australia", "ICC Cricket World Cup"), a match number, a stage ("Semi
Final") and, since V2-7's extraction, the group ("A", "1"). The names are inconsistent:

- The same tournament has had several names: the World Cup is "ICC World Cup", "ICC Cricket World
  Cup" and plain "World Cup"; the T20 World Cup "ICC World Twenty20", "World T20" and "ICC Men's
  T20 World Cup".
- A series is often named by the tour ("Australia tour of England and Scotland" for the 2005
  Ashes), and the same name returns every few years.
- Some matches have no name (under 1% of Tests and ODIs, 2% of T20Is).
- Group stages are often unlabelled (the 2004 Champions Trophy's pools, the 2019 World Cup's
  league), and long leagues (the World Cricket League) number their matches across rounds.
- Matches abandoned without a ball are not in Cricsheet, nor is any Afghanistan match, and a few
  matches are simply missing (the 2005 Ashes' third Test).

## Decision

- **An event is one name within a few weeks.** Matches of one major tournament (whatever
  Cricsheet called it; `config/events.yaml`), else of one event name, else (unnamed) of one pair
  of sides, form one event while each is within `GAP_DAYS` (45) of the last. An event between two
  sides is a **series**, between more a **tournament**. Built in the serving export of each
  national competition (`criciq_pipelines.events`), from the full warehouse's event columns; the
  limited-overs and Test model copies keep their columns.
- **Rounds.** A tournament's matches are grouped into Cricsheet's labelled groups (named by the
  edition where Cricsheet's "1" means "Super 12 Group 1"), its non-knockout stages ("Super
  Sixes"), and for unlabelled matches the groups of sides that played each other (one league, or
  pools); knockouts come last, in order of play. Tables count two points a win and one a tie or no
  result, then net run rate by the playing conditions (`team_matches`), then wins.
- **Honest scores.** A series' score counts the matches in the data; its numbering shows how many
  are missing (only where it numbers that series alone: at most seven matches), and the result
  says so. A series whose last match is within two weeks of the data's date reads "so far",
  because Cricsheet does not say how many matches are scheduled. Tournament tables carry a note
  that abandoned and Afghanistan matches are absent.
- **Known results.** `config/events.yaml` lists results the build must reproduce: every
  tournament champion with its final in the data (World Cups, Champions Trophies, T20 World
  Cups, World Test Championship finals) and complete Test series identified by their two sides
  and starting year. The export fails on a mismatch; the full-data tests also fail if any known
  result is not covered, so none is silently skipped.
- **Careers and comparisons stay per format.** Player careers add innings, averages, hundreds and
  fifties, best scores and figures per competition, and a headline ratings table: each rating is
  a percentile among that competition's own players, never a combined number. Compare can set a
  player in one competition beside a player in another; then each is read against its own par,
  only the rating skills both formats share are compared, and phases are not.
- **Lab notes across formats** (`criciq_ml.lab_formats`, `criciq-ml lab-formats`): the toss
  (the toss winner's share of results, since the toss is random) and home advantage (raw, and
  balanced for strength by averaging the home share at both ends of each pair of sides). Every
  competition's Analytics Lab shows them; the IPL's own notes stay with the IPL.

## Consequences

**Positive**
- Every international match belongs to a series or tournament page, and every major
  tournament's champion is checked against the known result on each build.
- The pages say what the data cannot: missing matches, unfinished series, tables without
  abandoned or Afghanistan matches.

**Negative / accepted trade-offs**
- Grouping by name and date can join two short series of the same name played within six weeks,
  or split a tour with a long gap; unnamed matches are grouped by sides and dates only.
- Series records count series of two or more matches that are over; one-off matches count in the
  meeting record only.
- Event ids (`2005-australia-tour-of-england-and-scotland`) come from the season and name, so a
  correction to Cricsheet's name changes the page's address.
