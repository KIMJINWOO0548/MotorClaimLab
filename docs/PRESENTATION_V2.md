# Frozen-result presentation v2

2026-11-01 KST. This is a bounded renderer improvement requested after the completed 0.1 study.

- Inputs remain `docs/evidence/benchmark/results.json` and `selection.json`. No fitting, reevaluation, seed/model selection or edits to the original ten published artifacts/expected hashes.
- Output goes only to a new `docs/evidence/presentation-v2/` directory. Its manifest records original input hashes and experiment provenance separately from renderer version **2.0**, renderer source hashes and newly derived artifact hashes.
- A compact three-row comparison keeps the mean baseline, validation and test scores together; text identifies the validation-selected model. Numeric columns use tabular figures and right alignment.
- Native `details` exposes complete data/code/git/seed/split/settings/environment provenance. Brief source context remains visible. Metrics and recorded conditions are separate; no compliance badges, fabricated KPI or default approval threshold.
- One horizontal interval depicts the saved selected-minus-baseline paired difference, with a zero reference, point/end labels and fixed-fit/split limitations. Missing/invalid bounds are unavailable, not a zero-width success. No independent per-model intervals are fabricated.
- Existing observed/predicted calibration, numeric bin ordering, aggregate tables, Sparse flags, truthful local/unverified provenance and escaping remain covered by regressions. Native table scrolling/focus and direct chart labels are used without JavaScript or external assets.
- Reference patterns: MLflow table/run context; Evidently metric-versus-check separation; scikit-learn exposure/calibration explanation. Exact URLs, licenses, rejected features and actual file mapping live in REFERENCE_ADOPTION.md.
- Browser file-URL access remains DENIED. Do not use another server/surface/raw CDP. Verification is limited to offline HTML/SVG structure, actual Matplotlib PNG inspection, targeted/full tests, wheel execution, Git-blob hash checks and real CI.

CLI extension: `python -m motorclaimlab render --results <saved results> --selection <saved selection> --output <new presentation directory>`. It reads existing aggregates and cannot execute a model. An existing output or inconsistent selection is an error.

Acceptance: source bytes unchanged; original ten hashes still match Git; derived manifest matches inputs, renderer and output files; compact table/provenance/paired zero-reference graph verified; no new service/cloud/runtime dependency; actual command exits and skipped browser evidence recorded before publication.
