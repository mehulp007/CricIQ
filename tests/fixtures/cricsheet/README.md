# Cricsheet test fixtures

A small subset of real IPL matches from [Cricsheet](https://cricsheet.org), chosen to
cover edge cases: golden scorecards, super overs, a no-result, D/L chases, umpire
miscounts, penalty runs, substitutions and retirements. See `scripts/make_fixtures.py`
for the list and the reason each match is included.

Cricsheet data is made available under the
[Open Data Commons Attribution License (ODC-BY 1.0)](https://opendatacommons.org/licenses/by/1-0/).
Files are minified but otherwise unchanged. `people.csv` holds only the register rows
for people who appear in these matches.

Regenerate with `uv run python scripts/make_fixtures.py`.
