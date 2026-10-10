# ADR-0011: One serving database per competition, and the site under /[competition]/

- **Status:** Accepted
- **Date:** 2026-10-07

## Context

V2-4 puts every T20 competition on the site: the IPL, men's T20Is and (by decision of the owner)
the BBL, PSL, CPL and SA20, each with the full set of pages, with ODI and Test cricket listed as
coming. Until now the API served one competition from one serving database (`serving.duckdb`,
the IPL's), plus the Player Lab of every competition from the players database (ADR-0009). Four
questions had to be settled:

- **Where each competition's data lives.** Matches, replays, teams, matchups and the simulator
  read about thirty serving tables through some 3,000 lines of repository and service code.
- **How the API names a competition**, and what happens to `/api/v1`.
- **How the web app's pages know their competition**, and what becomes of every existing URL.
- **What changes in content** for national sides and for leagues whose tables CricIQ cannot check.

## Decision

- **One serving database per competition**, all with the IPL's tables: `serving.duckdb` stays
  the IPL's (its regression gate and the live API's file name are unchanged) and the others are
  `serving-<competition>.duckdb` beside it. Each is exported from the competition's v1-shaped copy
  of the full warehouse (`criciq-data export` and every sync) and scored by `criciq-ml score` with
  the models serving that competition (ADR-0010). The IPL-only league-tables config (official
  tables, abandoned fixtures, voided matches) applies to the IPL alone.
- **`/api/v2/{competition}/...` throughout.** `get_db` picks the database a request's
  `{competition}` names, so every router, service and repository serves any competition
  unchanged; the Player Lab keeps reading the players database. `/api/v1` lives on only on
  `main`, the hosted IPL edition (v2 stays local, ADR-0016). `/meta` describes the competition (name, format, club or
  national, season names) and what serves it (`features.simulator` is false until a simulator
  version passes its backtest there).
- **Every data page moves under `/[competition]/`** (`/ipl/matches`, `/t20i/players/[id]`); the
  site root chooses a competition, and About and the write-up stay global. Old URLs redirect
  permanently (308) to `/ipl/...`. A switcher in the top bar keeps the same kind of page (a page
  about one match, player or team goes to its list) and a cookie remembers the choice for the
  global pages. Server components link through `CompetitionLink`, which prefixes the competition
  of the page being viewed, so shared components need no competition prop for their links.
- **Content follows the competition.** National sides have records by year and by opponent, not
  league tables or champions; league tables outside the IPL are labelled as computed (two points
  a win) because official tables may have used bonus points. A national side is at home in its
  own country (or the countries in `home_countries`), a league's ground is a side's home by how
  much it used it, and only the IPL limits home grounds to one country. Featured replays,
  Model Insights and the biggest swings are per competition; the Analytics Lab's notes are about
  the IPL and are linked only there.
- **Bounded caches.** Each database's derived objects (model terms, simulator engines for points
  in history, rating populations) live in an LRU-bounded cache, so asking about thousands of
  historical matches cannot grow memory without limit.

## Consequences

**Positive**
- One implementation serves every competition; adding ODI and Test (V2-5, V2-6) is a format's
  rules and a serving database each, not new routes.
- The IPL's serving data, models and pages are unchanged, and every old link still works.
- A competition without a model or simulator says so on its pages instead of showing placeholders.

**Negative / accepted trade-offs**
- Six serving databases (about 160 MB scored) instead of one; the API opens all of them at
  startup (about 1.5 s with warm-up); more than a free instance holds, so v2 runs locally
  (ADR-0016).
- Player tables exist in each serving database and in the players database; the Player Lab reads
  only the latter.
- League tables for the BBL, PSL, CPL and SA20 are not checked against official tables.

**Revisit when** the database count or size strains the API host: the competitions could then
move into schemas of one file, as the players database already does.
