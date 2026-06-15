# paperscout

A configurable literature radar and biomedical relation miner. Two CLI tools:

1. `radar`: score a set of papers (an OpenAlex query, a venue, an OpenReview venue, or your own
   CSV/JSON export) against research-interest "pillars" you define, and print a tiered list with
   a one-line reason per hit.
2. `triples`: mine the biomedical literature for drug-target-readout relations with a direction
   (up or down), backed by evidence sentences (PMIDs) and Open Targets mechanism-of-action targets.

## What it does

- Scores relevance against your pillar definitions rather than keywords. The radar compares each
  paper to each pillar's profile (TF-IDF cosine plus curated phrases) and tiers it, so you can
  triage hundreds of papers down to the relevant few and rerun it for each venue.
- Extracts structured relations, not just papers. The miner returns drug-to-readout statements
  with a direction and the source sentence.
- Pillars are data, not code: ship the generic defaults, or point the tool at your own pillar file
  kept out of version control (see below).
- No API keys required. OpenAlex, Europe PMC, Open Targets, and OpenReview are used without keys,
  and a SQLite cache keeps reruns fast and offline. Scoring is deterministic; an optional `--llm`
  pass refines reasons if `ANTHROPIC_API_KEY` is set.

## Install

```bash
git clone https://github.com/s-eun-young-g/paperscout
cd paperscout
uv venv && uv pip install -e .
export PAPERSCOUT_MAILTO=you@example.com   # better rate limits from OpenAlex/NCBI
```

## Usage

Radar:
```bash
# Live OpenAlex topic query:
paperscout radar --query "causal inference treatment effect estimation" --limit 100

# A venue and year via OpenAlex, or an OpenReview venue:
paperscout radar --venue "International Conference on Machine Learning" --year 2024
paperscout radar --openreview ICLR.cc/2024/Conference

# Your own paper dump (e.g. a conference not yet indexed):
paperscout radar --file accepted.csv          # columns: title,abstract,authors
paperscout radar --file papers.json           # [{title,abstract,authors:[{name,affiliation}]}]

paperscout radar -q "..." --format md -o out/radar.md
paperscout radar -q "..." --min-tier 1        # only the strongest hits
```

Triples:
```bash
paperscout triples --drug tocilizumab
paperscout triples --drug atorvastatin --readout LDL
paperscout triples --drug metformin --format md -o out/metformin.md
```

## Configuring your own pillars (and keeping them private)

paperscout ships a generic example pillar set (mainstream ML topics) so it runs out of the box.
To tune relevance to your own program, write a pillar JSON and point the tool at it. Files matching
`*.local.json` are gitignored, so your research focus stays out of the repo:

```jsonc
// pillars.local.json
[
  {"key": "CAUSAL", "name": "Causal inference",
   "profile": "a paragraph describing the research area, used for similarity",
   "terms": ["treatment effect", "confounding", "instrumental variable"],
   "weight": 1.0, "core": true}
]
```
```bash
paperscout radar --pillars pillars.local.json -q "..."
# or set it once:
export PAPERSCOUT_PILLARS=~/.config/paperscout/pillars.local.json
```
`core` pillars are the ones a paper must match to reach Tier 1. Edit `paperscout/radar/pillars.py`
only to change the public defaults.

## Example output

Committed in [`examples/`](examples/):
- [`examples/radar_causal_inference.md`](examples/radar_causal_inference.md): a radar run over a
  topic query, tiered against the default pillars.
- [`examples/triples_tocilizumab.md`](examples/triples_tocilizumab.md): mined tocilizumab-to-IL-6
  (down) with evidence sentences, PMIDs, and the Open Targets target (IL6R).

## How it works

Sources (OpenAlex, OpenReview, Europe PMC, Open Targets, file) produce normalized `Paper` and
`Triple` models. `radar.score` ranks papers (TF-IDF cosine plus a keyword rubric, pure Python);
`triples.extract` reads direction from sentence-level cues over co-mentions. Results render to
the terminal or markdown. A SQLite cache sits under every live fetch.

## Development

```bash
uv pip install -e ".[dev]"
pytest
```

## Notes

All data comes from public APIs (OpenAlex, Europe PMC, Open Targets, OpenReview) used within their
terms, with a descriptive User-Agent, throttling, and caching. Not affiliated with those services.
The direction extractor is a lexical heuristic: the dominant direction is reliable, but verify
individual evidence sentences for edge cases.

## License

MIT
