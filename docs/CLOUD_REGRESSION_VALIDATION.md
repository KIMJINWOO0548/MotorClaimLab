# Cloud regression increment

2026-11-01 UTC. Local branch `improve/experiment-regression-provenance`, based on
`fa7ade7c466a8a3f6ba8b6f2c0d2478121a03a8f`. This is an internal AI-assisted
implementation and review, not independent human or actuarial review.

## Changed behavior

The experiment previously read the input into memory before fitting, then
calculated its source hashes afterward. A file edited during fitting could
therefore produce completed results whose hashes described different bytes from
the observations used. A regression using only a hand-authored synthetic CSV
reproduced this behavior.

The run now captures MD5 and SHA-256 together before loading, checks source
identity after loading and before publishing completed results, and records the
initial provenance in running, failed and completed execution metadata. Changes
observed during loading stop before output creation. Changes observed during a
run preserve the failed execution record and partial split/selection evidence,
without writing completed results, reports or predictions. Package source-byte
fingerprints are captured before loading and checked before publication too.

The existing model definitions, seed, split algorithm, preprocessing, selection
criterion, bootstrap and evaluation are unchanged. The original full-data
experiment and every historical presentation remain preserved; no full-data
retraining or test-set optimization was performed.

## Regressions and commands

The new independent tests cover source changes during loading/fitting, code
changes, exact train-only fitting once, frozen validation selection before any
test predictions, repeated synthetic fits and train-only scaler statistics.
They also compare order/target-independent split membership with independently
calculated frozen SHA-256 digests for synthetic policy IDs 1 through 300.

Observed TDD sequence: **3 failed, 3 passed** before the implementation;
**6 passed** after it. The unchanged baseline full suite had **112 passed**.
Final Linux/Python 3.12.14 suite: **118 passed**, exit 0. Ruff lint/format,
hash-locked dependency consistency, wheel/sdist build, distribution exclusion,
original Git-blob evidence and current presentation integrity checks all passed.
All **41** pre-existing `docs/evidence/` files remain byte-identical to the
baseline. Exact logs are recorded in the companion local evidence package.

Run from the repository root with Python 3.12 and a dedicated virtual environment:

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m build --no-isolation
python scripts/check_distribution.py
python scripts/check_evidence.py
python scripts/check_presentation.py
python -m pip check
```

## Claims and limits

- The checks detect source/code byte changes observed at the recorded boundaries;
  they do not lock files, detect transient changes restored between checks, or
  authenticate loaded runtime code, authorship, rights or provenance declarations.
- The Git commit and package source digest describe separate aspects of a run.
  A commit alone does not identify an uncommitted checkout. The code digest is a
  fingerprint of package source files on disk, not a runtime attestation.
- Repeated-fit equality was tested on a small synthetic fixture in one Linux
  environment. It is not proof of bitwise equality across platforms or versions.
- No raw source data was downloaded in this increment. Historical full-data
  metrics are preserved and were not independently recomputed here.
- The source has no reliable observation-date field. Policy holdout is not
  chronological validation; current Korean insurance performance is untested.
- Remote CI, push, PR, merge and deployment were not performed. Existing saved
  CI evidence refers to earlier commits only.
- Browser capture/layout checks remain unrun. `docs/DESIGN.md` records the prior
  file-URL denial and explicitly prohibits alternate server/browser workarounds.
  The original aggregate HTML and charts are preserved as source artifacts,
  not newly claimed browser screenshots.

Exact commands, versions, exit codes, baseline/final logs, original evidence
hashes, restoration commands and a Git bundle/patch are in the local companion
package, also mirrored to a fresh ignored `reports/runs/` directory. Per-policy
records, predictions, raw data and fitted models are excluded from that package.
