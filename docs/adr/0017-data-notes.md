# ADR-0017: Daily notes are written by rules, from CricIQ's own data only

- **Status:** Accepted
- **Date:** 2026-11-08

## Context

The site wanted a short daily account of what happened in men's cricket: results, the moment
each match turned, milestones and records. The usual ways to get one are a news feed or API
(licences, keys and a source outside the data) or a language model writing the text (cost per
note, and sentences whose figures can't be checked against anything). Both would also put words
on the site that CricIQ's own data doesn't stand behind.

## Decision

- **Only the serving databases.** `criciq_pipelines.notes` reads the eight competitions'
  serving databases and nothing else: no news source, no outside API and no model writing text.
- **Fixed rules, one per item.** Each item (result, turning point, match-winner, milestone,
  record, standings) is a sentence builder with its own threshold, so every word of a note can
  be traced to a rule and every figure to a table. The same data always gives the same notes.
- **Whole archive, rebuilt each time.** One note for every day a match ended, rebuilt in full
  (about 75 seconds for every competition) by `criciq-data notes`, every sync and every full
  build. Rebuilding only the changed days would save little, since the history every
  milestone and record depends on has to be read either way.
- **Honest about its limits.** Model figures (win-probability swings, win probability added)
  are labelled model estimates; milestones and records say they are counted "in CricIQ's data",
  and international milestones leave out players whose careers may have begun before it; a
  series with matches missing from the data gets no series score. Every note ends with the
  method line.
- **Optional to serve.** The notes live in their own database (`notes.duckdb`), published like
  the serving databases and carried in the data zip. The API opens it once it appears and
  answers with no notes without it, so an older data snapshot still works.

## Consequences

**Positive**
- Free, automatic and deterministic; a test parses the figures out of the notes and checks
  each one against its source table.
- A note can never report anything the data doesn't hold, and a correction to the data corrects
  the note on the next sync.

**Negative / accepted trade-offs**
- The prose is plain and repetitive by design: a fixed sentence per kind of item.
- Notes appear only once Cricsheet publishes the matches, usually a day or two after play.
- Context outside the data (injuries, team news, why a player missed a match) is never there.
