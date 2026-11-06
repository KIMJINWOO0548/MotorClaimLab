# Partition review from frozen aggregates — renderer 3.4

2026-11-06 UTC. Overall agreement can hide segment cancellation: observed=predicted=20 claims can consist of +8 and −8 group gaps. Renderer 3.4 makes the net gap (0) and absolute group-gap sum (16) visible together, then links to complete group tables with support, largest under/over differences and the saved Sparse context. This is descriptive investigation of saved aggregates, not a new model result, actuarial recommendation or business threshold.

## Reference and critical comparison

REA 6.8.0 actually captured the official [Evidently regression documentation](https://docs.evidentlyai.com/metrics/preset_regression), which describes actual/predicted plots, error distributions and segment exploration. Evidently's [official README](https://github.com/evidentlyai/evidently/blob/main/README.md) links the [public live demo](https://demo.evidentlyai.com). The actual REA demo attempt returned exit 1, non-retryable execution failure: navigation failed before the initial state was captured. No sample report UI was observed and no unchanged retry was made. Interactive reference workflow and competitor performance remain NOT_RUN/blocked; documentary evidence is separate. Metadata/digests are in `replica/phase2/rea-evidence.json`.

Our renderer 3.3 already showed all 13 groups, but required scanning three wide tables to identify offsetting errors. The new partition index provides an investigation entry point without changing models, data, split membership, seed, selection, confidence interval or saved metrics. No third-party source, private API, assets or report copy is reused. Native links/disclosures preserve offline use with JavaScript disabled.

Rows, positive exposure and nonnegative observed/predicted counts are checked separately against the selected model's saved test metrics. Duplicate group names, missing/invalid/nonfinite/bool/overflow aggregates or inconsistent totals yield N/A for combined gaps, shares and largest findings. Numeric agreement is not proof of row membership or disjointness. Dimensions overlap and must not be added. Largest count gaps are an exploration order, not a fairness, significance or risk ranking; exact ties keep saved order.

## Validation

| Check | Actual result |
|---|---|
| Baseline full suite | 152 passed |
| New independent cases | 15; initial absent API RED, hand-calculated and invalid-state cases GREEN; huge-integer overflow separately reproduced RED and fixed |
| Final full suite after manifest correction | 167 passed, 47.73 s during other host work |
| Ruff lint and format | Exit 0; 29 files already formatted |
| Version-boundary regressions | Only 2 expected renderer-version literals advanced 3.3 → 3.4; other assertions retained |
| Fresh manifest status regression | Historical SKIPPED/DENIED default reproduced RED; fresh generation now records NOT_RUN separately; 44 affected tests passed |
| Replica selected-role contrast | 7/7 AA; minimum 4.85:1 |
| Impeccable rendered-HTML detector | Exit 2: 16 warnings (10 tiny text, 6 table padding), identical types/counts on preserved 3.3 baseline; remaining chart-label/table warnings are not a full accessibility pass |
| Actual Chrome, JavaScript disabled | Exit 0; 3 dimension links and native Enter disclosures; 390 px without page overflow; no remote requests |
| Visual review | Desktop and mobile review screenshots inspected: no new-block clipping/overlap observed |
| Print | PDF generation succeeded; pagination remains visually unverified |

New tests use hand-authored aggregates, exact support/share/net/absolute calculations, all four reconciliation fields independently, duplicate groups, invalid numeric types, exact ties, overflow, escaping, empty input, overlapping dimensions and immutable input. Overflow fail-closed checks apply to the new partition summary; the renderer is not a general schema validator for arbitrary untrusted JSON. Existing no-model-execution/provenance tests still pass. Sparse thresholds are unchanged. All 50 prior tracked evidence files, including renderer 3.3, are byte-identical. The new 8 artifacts, 2 inputs and 2 renderer-source hashes were verified; HTML/Markdown hashes match the final measured outputs exactly.

## Local renderer cost, not model or competitor performance

`scripts/benchmark_report.py` runs HTML+Markdown rendering in three fresh Python 3.12.10 processes per revision on Windows 11 build 26200. Input SHA-256 is `3585e11b57460165521a43db7b21d26dd11330c47affcec820c450c0781e1a74` in every run. RSS is whole-process peak working set including imports; render wall time covers the two render calls. It is not a 678,013-row training measurement or a UI task-time benchmark.

| Revision | Render seconds, 3 runs | Median peak RSS | HTML / Markdown bytes |
|---|---|---:|---:|
| 3.3 before | 0.2658674 / 0.3214499 / 0.2918098 | 66,035,712 B | 60,563 / 6,521 |
| 3.4 final | 0.2123222 / 0.2067039 / 0.2099769 | 66,195,456 B | 64,448 / 8,088 |

The richer HTML adds 3,885 B (6.4%); Markdown adds 1,567 B; median process peak RSS is 159,744 B higher. The lower time readings do not establish a causal speedup: these are three sequential local runs, later runs can benefit from warm filesystem/font caches and scheduler conditions, and an earlier intermediate 3.4 check overlapped the baseline timing range. No rendering algorithm speedup or external-product advantage is claimed. Exact records, source/output hashes and the intermediate check are retained in the curated measurement JSON.

Reproduction with existing dependencies:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python scripts/benchmark_report.py --results docs/evidence/benchmark/results.json --output reports/runs/fresh-cost.json --repeats 3
python -m motorclaimlab render --results docs/evidence/benchmark/results.json --selection docs/evidence/benchmark/selection.json --output reports/runs/fresh-presentation
python scripts/check_segment_review_browser.py --report reports/runs/fresh-presentation/report.html --output reports/runs/fresh-browser
```

The browser harness uses an existing Playwright/Chrome runtime, loopback-only static serving, JavaScript disabled, native keyboard links/disclosures and 390 px overflow checks. It produces a PDF for separate visual pagination review; PDF creation itself is not a print-layout pass.

Actual browser result hashes and source binding: [browser-checks.json](evidence/competitive-depth/browser-checks.json). Own review screenshots: [desktop](evidence/competitive-depth/desktop-review.png), [mobile](evidence/competitive-depth/mobile-review.png). The exercised report SHA-256 is `58a2f5f71fc64d6db17ba56f0b3ecb0f349f1ae603c6805a39ebd12f0aecd236`, identical to the generated manifest and final measurement output. The generation manifest correctly remains NOT_RUN at generation; later browser verification is separate.

## Remaining gaps

No current Korean validity, severity/cost model, operational use, measured savings, insurer endorsement or external human/actuarial review is claimed. Row-level error distribution, cross-model group residuals, temporal/current-reference monitoring, live ingestion and authenticated product behavior remain gaps. The scoped Replica matrix is 7 rows (raw weighted 67.6; 3/4 must complete), not a product score, market-wide parity or superiority claim. Screen-reader and full print-pagination/200% zoom verification require their own evidence.
