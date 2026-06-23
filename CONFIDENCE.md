# paperscout confidence layer

A writeup of the calibrated confidence layer added to paperscout: what it does, how it is built, why it cannot break the firewall, and how to evaluate whether it helps.

## The problem

paperscout currently emits a binary outcome per `drug -> readout` pair: it commits a signed direction (up or down) or it abstains. That is the right safety behavior for an oracle whose first job is to never commit a wrong sign. But it throws away real information: a prediction backed by 21 unanimous human-trial abstracts is treated the same as one backed by 3 abstracts with a dissenter, even though the first is far more trustworthy.

The goal is to expose that uncertainty as a calibrated confidence score per committed prediction, so downstream coupling analyses can weight strong predictions more heavily than weak ones, without changing which predictions get signed.

## The one rule that governs the design

Confidence is computed strictly after sign generation and is read-only. It never calls into or alters `commit_direction`, the vote tally, or the abstain decision. A prediction is signed (or abstained) exactly as before, and the score is attached afterward. This means the project's primary safety metric, near-zero wrong-direction, is structurally unchanged: the layer cannot flip a sign or un-abstain a split, by construction.

In code: `commit_direction(...)` runs first and sets the direction. `score_triple(triple)` then reads the committed triple and returns a `ConfidenceBreakdown`. The extractor attaches it as `triple.confidence`. Nothing flows back the other way.

## The signals

The score in [0, 1] is a transparent, deterministic blend of three families, all already captured by the miner (no ML, no extra network calls).

### 1. Quantity

How many signed abstracts support the call, with diminishing returns.

```
quantity = 1 - exp(-n_signed / 5)
```

n_signed = 2 gives 0.33, 5 gives 0.63, 10 gives 0.86, 21 gives 0.98. More evidence always helps, but the 30th abstract matters less than the 3rd.

### 2. Consistency

The directional agreement among the signed abstracts, mapped so a near-split scores low and unanimity scores high.

```
agreement   = max(n_up, n_down) / n_signed          # 0.5 .. 1.0
consistency = clamp((agreement - 0.5) / 0.5, 0, 1)   # 0.5 agreement -> 0, 1.0 -> 1
```

This is what makes 21 down / 0 up (consistency 1.0) outrank 3 down / 1 up (agreement 0.75, consistency 0.5) even though both commit "down." Committed triples always have agreement at least 0.75 (the commit gate requires the minority fraction to be within 0.25), so their consistency lands in [0.5, 1.0].

### 3. Quality

The strength of the evidence behind the majority direction. Computed only over the abstracts that voted with the committed direction, so dissenters do not inflate it.

- Study model (the "MODEL used" axis), weighted: human trial 1.00, human observational 0.80, animal 0.50, in vitro 0.35, unknown 0.60.
- Recency, from the most recent supporting paper: 2018 or later 1.0, 2010 to 2017 0.9, 2000 to 2009 0.8, older 0.7, unknown 0.85.
- Citation and review bump: a small additive term from the max citation count and whether any supporting paper is a review, capped at 0.15.
- Cohort bump: a small additive term, log-scaled in the largest reported cohort size, capped at 0.10.

```
quality = clamp(model_weight * recency + citation_bump + cohort_bump, 0, 1)
```

Study model and cohort size are not in the source metadata, so they are derived from the evidence text with transparent lexical cues, in the same spirit as the direction extractor:

- human trial: "randomi", "double-blind", "placebo-controlled", "clinical trial", "phase ii/iii", "rct", "crossover trial"
- human observational: "patients", "subjects", "participants", "cohort", "cross-sectional", "case-control", "observational"
- animal: "mice", "mouse", "murine", "rat", "rodent", "zebrafish", "in vivo", "knockout"
- in vitro: "in vitro", "cell line", "cultured", "hepatocyte", "hepg2", "thp-1", "ex vivo"

When an abstract carries cues for more than one model, the highest-priority one wins (a human trial reading dominates a co-mentioned cell arm). Cohort size is parsed from patterns like "n = 1,234" or "200 patients."

Year, citation count, and review status come straight off the existing `Evidence` metadata, so only model and cohort needed new extraction.

## Combining them

```
score = quantity * (0.5 + 0.5 * consistency) * (0.6 + 0.4 * quality)
```

- Quantity is the spine.
- Consistency scales it: a near-split halves the contribution, unanimity keeps it full.
- Quality modulates it within a floor of 0.6: because the sign is already committed, quality adjusts confidence but never zeroes a committed call. A human-trial-backed prediction scores higher than an in-vitro-only one at the same quantity and consistency.

Bands: score 0.70 or higher is "high", 0.45 to 0.69 is "moderate", below 0.45 is "low".

## What is exposed

`Triple.confidence` is a `ConfidenceBreakdown` with every component broken out, not just the headline number: `score`, `band`, `quantity`, `consistency`, `quality`, `n_signed`, `agreement`, `dominant_model`, `model_mix`, `mean_year`, `max_cited_by`, `n_reviews`, `cohort_max`. The terminal and markdown reports show the score, band, and dominant model per triple, and tag each evidence line with its inferred study model.

## Worked examples

```
case                                    dir       score  band      quantity consistency quality  model
21 down / 0 up (human obs)              down      0.93   high      0.98     1.00        0.85     human_observational
3 down / 1 up (human obs)               down      0.39   low       0.55     0.50        0.85     human_observational
8 down, human RCT                       down      0.80   high      0.80     1.00        1.00     human_trial
8 down, human observational             down      0.78   high      0.80     1.00        0.95     human_observational
8 down, animal (mouse)                  down      0.66   moderate  0.80     1.00        0.55     animal
8 down, in vitro (cell line)            down      0.61   moderate  0.80     1.00        0.40     in_vitro
25 down, large RCT, cited 300           down      0.99   high      0.99     1.00        1.00     human_trial
2 down, in vitro only                   down      0.25   low       0.33     1.00        0.40     in_vitro
3 down / 3 up (split)                   unclear   0.33   low       0.70     0.00        0.85     human_observational
```

The last row is the firewall in action: a 3/3 split still abstains (direction "unclear"), and scoring it does not change that.

## Tests

`tests/test_confidence.py` (47 tests pass overall, ruff clean) locks in:

- the headline example, 21/0 outranks 3/1;
- quantity and consistency are monotonic;
- the study-model ordering human trial >= observational >= animal >= in vitro;
- the model classifier and cohort-size parser on representative strings;
- the score stays in [0, 1] and bands correctly;
- and, explicitly, that scoring never changes a committed direction and never un-abstains a split.

## The research question, and how to evaluate it

The motivating question is whether richer confidence estimates improve predictive power beyond the commit/abstain framework without sacrificing near-zero wrong-direction.

- The second half is structurally guaranteed here. Because confidence never feeds the sign, the benchmark's wrong-direction count is identical with or without this layer. The tests enforce it.
- The first half needs a downstream evaluation, not a unit test. The way to test it: in the predict-decode coupling, weight each comparison by the prediction's confidence and check whether the sign-agreement rate (and effect attribution) rises versus the unweighted commit/abstain baseline. A useful intermediate check is a calibration plot on the gold set: confidence should be higher for the correct, well-supported triples than for the thin or abstained ones. The scoring needed for both is now in place.

## Limitations and honest notes

- The score is a hand-designed, transparent blend, not a fitted calibration. The gold benchmark is small and almost entirely correct, so there is not enough labeled error to fit a meaningful logistic model yet. A transparent score that ranks sensibly is the honest v1; true probability calibration waits for more labeled outcomes.
- Study model and cohort size are heuristic text inference, so they will miss or misread some abstracts. They are weighted modestly and never override the sign, so the cost of a misread is a slightly mis-set confidence, not a wrong prediction.
- The weights and saturation constants are chosen, not learned. They are exposed as module constants so they can be tuned against the downstream coupling result.

## Files

- `paperscout/triples/confidence.py` - the layer (classification, extraction, scoring).
- `paperscout/models.py` - `Triple.confidence` field (forward-ref, read-only).
- `paperscout/triples/extract.py` - attaches the score after `commit_direction`.
- `paperscout/triples/report.py` - surfaces confidence and per-evidence model in reports.
- `tests/test_confidence.py` - the test suite.

Committed on branch `feat/confidence-layer`.
