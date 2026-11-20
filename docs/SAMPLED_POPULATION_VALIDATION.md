# Renderer 3.2: consistent sampled-population context

2026-11-02 UTC. Local improvement from
`1bfe1faf65a2b0785f5177495f0a73e5d9641b8e`, branch
`improve/sampled-population-context`. Internal AI-assisted implementation and
read-only review, not external human or actuarial validation.

## Reproduced error and bounded fix

The supported `run --max-rows` path audits the full local input, then samples
records before splitting, fitting and evaluation. The HTML opening paired the
sampled `study.rows` with the full-input `audit.exposure`.

A hand-authored 300-row synthetic fixture with `--max-rows 120` reproduced
`120 rows / 200.00 exposure-years` in the opening. The sampled population has
**84.75 exposure-years**, independently calculated from the published hash
sampling protocol; saved split totals and sample EDA agree. The full-input audit
correctly remains 300 rows and 200 years.

Renderer **3.2** now pairs study rows with the complete saved train/validation/test
exposure total, using `math.fsum`. All three splits must exist, have positive
finite numeric exposure and integer row counts, and their row total must match
the study. Booleans, numeric strings, nonfinite/negative/zero exposure, missing
metadata, mismatched populations, lossy integer conversion and conversion/summation overflow produce
**N/A**, without silently substituting the full-input audit. HTML and Markdown
label the full-input audit separately. This sums saved context; it does not
recompute predictions, evaluation metrics or confidence intervals.

No experiment, model, sampling, splitting, seed, validation selection or held-out
evaluation implementation changed. Frozen aggregate results and all previous
report/figure/manifest bytes are preserved. No real dataset was downloaded or
rerun, and no model/test result was optimized.

## Historical and current renderer verification

The v3.1 manifest keeps its original expected hashes. Validate its inputs,
manifest and artifacts against the current Git HEAD (or index with `--staged`),
and its two renderer source files against their actual immutable source commit:

```bash
python scripts/check_presentation.py --renderer-ref 6efb433791c012e273ef12a6a6fcb28dfd525b51
```

`--renderer-ref` accepts only an existing full 40-character commit SHA, affects
only the two allowlisted renderer source reads, and never fetches an object.
Abbreviations, branch names, unavailable commits and noncommit objects are
rejected. CI checks out full history to make this historical source available.
Input or artifact mutation still fails under this option. Omitting the option
preserves the strict current-source comparison: current v3.2 source does not
match the historical v3.1 manifest and therefore fails that comparison.

Current v3.2 is validated separately on fresh synthetic saved aggregates. Its
new manifest must identify current renderer source hashes, all eight output
hashes, unchanged input hashes and `model_execution: false`. Tests forbid model
fitting or experiment execution in saved rendering. No v3.1 output or manifest
is regenerated to make a guard pass.

## Actual verification and reproduction

Baseline: **118 passed**. Before implementation, new population/historical-source
tests produced **17 failed, 5 passed**. After implementation, the affected report
and guard suite passed **57 tests**. A cross-review independently reproduced a
row-count precision edge above `2**53` as a failing test; exact count comparison
fixed it, bringing the affected suite to **58 passed**. Final full suite:
**143 passed**. Lint, format, dependency consistency, wheel/sdist build,
distribution exclusion, original Git-blob evidence and historical v3.1 source
verification passed. Fresh v3.2 output verified both current source hashes and
all eight artifact hashes, with preserved saved-input bytes and no model
execution during rendering. All 41 historical evidence files and the 45 files
of the first delivery package remain byte-identical. Exact commands, exit codes,
source hashes and restoration files are in the fresh local evidence package and
mirrored to a new ignored `reports/runs/` directory.

Use the existing declared hash-locked environment, with no additional package:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m pip check
python -m build --no-isolation
python scripts/check_distribution.py
python scripts/check_evidence.py
python scripts/check_presentation.py --renderer-ref 6efb433791c012e273ef12a6a6fcb28dfd525b51
```

Browser capture/layout/accessibility remains unrun under the existing recorded
file-URL denial and prohibition on alternate surfaces. New aggregate HTML and
figure files are local source artifacts, not claimed browser screenshots.
No GitHub operation, push retry, new authentication, remote CI or deployment
occurred in this quality round. The earlier push remains denied with HTTP 403.
