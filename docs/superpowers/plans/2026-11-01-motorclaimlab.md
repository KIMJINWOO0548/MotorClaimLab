# MotorClaimLab Implementation Plan

> For agentic workers: execute bounded tasks under the user's authorized design-and-build request. Preserve TDD and independent whole-project review.

**Goal:** Publish a reproducible historical automobile insurance frequency study with actual aggregate results and explicit limits.

**Architecture:** Small Python package and offline CLI. Separate source validation/splitting, train-only models, exposure-weighted evaluation, report rendering and orchestration.

**Tech Stack:** Python 3.12, NumPy, pandas, SciPy, scikit-learn; pytest, Ruff, build. Installation requires the pending user approval.

**Spec:** ../../DESIGN.md

## Global constraints

- Seed 20261101; 60/20/20 target-independent policy hash split.
- OpenML 41214 v1 with published MD5 and computed SHA-256.
- No raw observations, policy identifiers, fitted model binaries or credentials in Git.
- Retain valid unusual rows; no silent clipping. Train-only preprocessing; validation-only model selection.
- Weight frequency fitting and evaluation by Exposure. Test is descriptive final evidence only.
- No output overwrite, network in tests, automatic dependency installation, deployment or business-impact claims.

## Review focus

- Invalid count/exposure or duplicate IDs must stop rather than contaminate metrics.
- Row-order changes and target edits cannot change policy split membership.
- Unknown held-out categories cannot refit encoders or fail predictions.
- Unequal exposure must change both baseline and metric arithmetic correctly.
- Existing output paths and HTML-like category values must not corrupt files or execute markup.

## Task 1: Data and evaluation contracts

Files: data.py, evaluation.py, tests/test_data.py, tests/test_evaluation.py. Interfaces exactly as DESIGN.md.

- [x] Write tests for malformed/nonfinite values, duplicate IDs, stable disjoint split and seeded sample.
- [x] Observe expected RED before implementation; preserve command/exit evidence.
- [x] Implement audit, ARFF parsing, bounded source download and hashing.
- [x] Write independent arithmetic tests: weighted mean/count, deviance, calibration, paired bootstrap.
- [x] Observe RED, implement evaluation, run affected and full tests.
- [x] Review staged files, commit and push data/evaluation milestone (751e6f7).

## Task 2: Models

Files: models.py, tests/test_models.py. Consumes validated train DataFrame; produces mean/poisson_glm/poisson_hgb predictors.

- [x] Tests for exposure-weighted mean, finite positive predictions, unseen categories and train-only fit.
- [x] Observe RED, implement fixed model pipelines, run affected/full suite.
- [x] Treat convergence failure as failure; do not hide warnings.
- [x] Commit tested model implementation (751e6f7).

## Task 3: Reproducible CLI, EDA and report

Files: eda.py, experiment.py, report.py, __main__.py, tests/test_experiment.py, tests/test_report.py.

- [x] Test real temporary CSV/ARFF input, validation model choice, overwrite refusal, CLI exit behavior, SQL totals and escaped HTML.
- [x] Observe RED, implement run orchestration, local-only predictions/splits, sanitized aggregate results.
- [x] Generate standalone HTML/Markdown/SVG/PNG; inspect actual offline charts and HTML/SVG structure.
- [ ] SKIPPED / DENIED: actual browser desktop/mobile audit. User explicitly forbids alternate surfaces/server workarounds after file URL policy rejection.
- [x] Run full tests and lint; commit and push working offline pipeline (751e6f7).

## Task 4: Actual benchmark and public evidence

Files: docs/evidence/, docs/RESULTS.md, README.md, docs/STATUS.md, .github/workflows/ci.yml.

- [x] Download pinned source; record published checksum and actual dimensions.
- [x] Execute frozen protocol, record source/code/settings/environment and timing.
- [x] Review exact results and limitations; curate aggregate-only artifacts for publication.
- [x] Independent AI review of leakage, metrics, outputs and packaging; fix material findings with RED/GREEN.
- [x] Full tests, Ruff, build and isolated-wheel smoke; run/view actual GitHub CI after push (41218810116, three jobs success).
- [x] Confirm public remote/main and clean working tree at dda7b54; CI 41219758581 success. Actual results and browser SKIPPED are recorded in README/STATUS/VALIDATION.
