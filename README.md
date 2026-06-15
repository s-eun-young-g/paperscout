# paperscout

A small, configurable **literature radar + biomedical relation miner**. Two CLI tools:

1. **`radar`** — score any set of papers (an OpenAlex query, a venue, an OpenReview
   venue, or your own CSV/JSON export) against **research-interest "pillars" you define**,
   and print a **tiered read/triage list** with a one-line *why* per hit.
2. **`triples`** — mine the biomedical literature for **drug → target → readout** relations
   *with direction* (↑/↓), backed by evidence sentences (PMIDs) and Open Targets
   mechanism-of-action targets.

## Why it's useful

- **Relevance by *your* definition, not keywords.** The radar compares each paper to the
  *profile* of each research pillar (TF-IDF cosine + curated phrases) and tiers it, so you can
  triage hundreds of accepted papers down to the handful that matter to your work — and rerun
  it for every venue.
- **Outputs structured relations, not just PDFs.** The miner extracts `drug → readout`
  statements with a direction and traceable evidence, so the result is data you can act on.
- **Configurable & private.** Pillars are data, not code: ship the generic defaults, or point
  the tool at your own pillar file kept **out of version control** (see below).
- **Key-free & cached.** OpenAlex, Europe PMC, Open Targets, and OpenReview are all used
  without API keys; a SQLite cache keeps reruns fast and offline. Scoring is deterministic and
  transparent (an optional `--llm` pass can refine reasons if `ANTHROPIC_API_KEY` is set).

## Install

```bash
git clone https://github.com/s-eun-young-g/paperscout
cd paperscout
uv venv && uv pip install -e .
export PAPERSCOUT_MAILTO=you@example.com   # nicer rate limits from OpenAlex/NCBI
```

## Usage

### Radar — tiered relevance list
```bash
# Live OpenAlex topic query:
paperscout radar --query "causal inference treatment effect estimation" --limit 100

# A venue + year via OpenAlex, or an OpenReview venue:
paperscout radar --venue "International Conference on Machine Learning" --year 2024
paperscout radar --openreview ICLR.cc/2024/Conference

# Your own accepted-paper dump (e.g. an upcoming conference not yet indexed):
paperscout radar --file accepted.csv          # columns: title,abstract,authors
paperscout radar --file papers.json           # [{title,abstract,authors:[{name,affiliation}]}]

paperscout radar -q "..." --format md -o out/radar.md
paperscout radar -q "..." --min-tier 1        # only the strongest hits
```

### Triples — drug → target → readout with direction
```bash
paperscout triples --drug tocilizumab
paperscout triples --drug atorvastatin --readout LDL
paperscout triples --drug metformin --format md -o out/metformin.md
```

## Configuring your own pillars (and keeping them private)

`paperscout` ships a **generic example** pillar set (mainstream ML topics) so it runs out of
the box. To tune relevance to your own program, write a pillar JSON and point the tool at it —
**this file is gitignored** (`*.local.json`), so your research focus never lands in the repo:

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
# or set it once, globally:
export PAPERSCOUT_PILLARS=~/.config/paperscout/pillars.local.json
```
`core` pillars are the ones a paper must match to reach Tier 1. Edit `paperscout/radar/pillars.py`
only if you want to change the *public* defaults.

## Example output

(committed in [`examples/`](examples/))
- [`examples/radar_causal_inference.md`](examples/radar_causal_inference.md) — a radar run over a
  topic query, tiered against the default pillars.
- [`examples/triples_tocilizumab.md`](examples/triples_tocilizumab.md) — mined
  `tocilizumab → IL-6 ↓` with evidence sentences + PMIDs and the Open Targets target (IL6R).

## How it works

`sources` (OpenAlex / OpenReview / Europe PMC / Open Targets / file) → normalized
`Paper`/`Triple` models → `radar.score` (TF-IDF cosine + keyword rubric, pure-Python) or
`triples.extract` (sentence-level direction cues over co-mentions) → `report`
(terminal / markdown). A SQLite cache sits under every live fetch.

## Development
```bash
uv pip install -e ".[dev]"
pytest
```

## Notes
All data comes from public APIs (OpenAlex, Europe PMC, Open Targets, OpenReview) used within
their terms, with a descriptive User-Agent, throttling, and caching. Not affiliated with those
services. The direction extractor is a transparent lexical heuristic — the dominant direction
is reliable, but verify individual evidence sentences for edge cases.

## License
MIT
