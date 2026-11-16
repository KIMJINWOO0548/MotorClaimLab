# Exposure, input provenance, and saved-result checks

This increment covers ledger MC1–MC4 on `improve/exposure-provenance-20261116`, starting at `816e5edbfa1e8bd0a9d7f9c058f39a5070dedae0`. Development and evaluation inputs for the increment are synthetic. The published historical aggregate and prior presentation files are retained.

## MC1. Use the exposure of the measured population

| Measure | Numerator and denominator | Population |
| --- | --- | --- |
| Audit and split support | Exact row count, exact claim count, and sum of observed exposure-years are separate totals | Audit covers the full admitted source. Train, validation, and test each cover their own assigned rows. The study exposure is the sum across those three partitions. |
| Observed and predicted frequency | Sum of observed counts or sum of predicted rate × policy exposure, divided by sum of exposure-years | Training baseline, validation/test metric, SQL area, calibration bin, or fixed segment, each with its own contributing rows |
| Weighted MAE and Poisson deviance | Sum of exposure-weighted errors divided by sum of exposure-years. Count-scale arithmetic avoids forming an overflowing ratio of extreme positive rates. | The displayed split, bin, or segment only |
| Observed/predicted ratio | Observed claims divided by predicted claims. Zero or unrepresentable denominator ratio is unavailable. | Same saved split, bin, or segment for both counts |
| Segment support share and count gap | Group exposure divided by the selected model's test exposure. Count gap is observed minus predicted claims. | Compare within each dimension. Driver age, vehicle age, and area can describe the same policy. |
| Pure premium in the synthetic oracle | Sum of explicit nonnegative monetary losses divided by exposure-years | The frequency source has no loss amounts. The CLI report displays N/A. The same policy rows and exposure support the synthetic helper. |

Zero, negative, NaN, and infinite exposures reject the input, as do empty sources, empty train/validation/test partitions, and unrepresentable totals. Unusual positive exposures such as values above one year remain in the audit and analysis without clipping. An evaluation whose derived frequency cannot be represented fails explicitly. Fixed bands with no policies have no denominator and are omitted. Populated calibration bins and segments remain visible and carry reasons for support below 50 rows or 10 exposure-years. SQL orders groups while Python sums exact integer claims and accurately sums exposure, including counts beyond SQLite's signed 64-bit SUM capacity.

## MC2. Bind parsing and provenance to a single source capture

A capped block read writes to a private temporary file while computing SHA-256 and MD5 on the same blocks. The parser rewinds that handle and reads its captured bytes. Header/row validation, sampling, splitting, preprocessing, and fit consume the resulting frame. Original-path and opened-descriptor metadata and byte lengths are checked during acquisition. The experiment also checks original-path metadata after parsing and before publishing results. The source SHA identifies the admitted file bytes. The train membership SHA identifies the exact ordered policy IDs assigned to training. The configuration and code fingerprints identify the recorded transformation and model settings. The snapshot closes automatically and is absent from public outputs.

The pre-fix transient-swap regression recorded the original SHA while fitting changed claim counts. Additional synchronized acquisition probes cover an overwrite, truncation, replacement, transient redirection, and original mutation after capture. Metadata checks detect observable changes. A filesystem writer that conceals all metadata changes remains outside this detection guarantee. The captured bytes still supply both the digest and the parse. This does not attest to the source's authenticity, ownership, or atomicity on an adversarial filesystem.

## MC3. Reject inconsistent saved results before rendering

`motorclaimlab render` reads the selected JSON inputs, rejects duplicate keys and nonfinite numbers at any depth, and checks the required run fields before creating output. New runs require explicit selection or a sibling `selection.json`. Shared run identity version 1 combines captured source SHA-256/MD5, recorded code hash, canonical settings hash, and canonical split-summary hash. The renderer also cross-checks validation-only selection and its scores, settings, split and metric support, exposure-based rates, and the bootstrap declarations. Test metrics never set model selection. The exact legacy results and selection published with the benchmark remain readable under the frozen archive exception. The manifest distinguishes that legacy input from a current pair.

Identity checks are consistency checks between inputs. Verification against malicious coordinated edits would require an independently trusted reference or signature. Current run admission requires the original data through its usual CLI. Rendering uses aggregates without loading raw policies or fitting.

## MC4. Paired bootstrap support and abstention

The PCG64 seed is recorded. Every draw resamples the same policy indices for the selected and mean models. The statistic is the difference in their exposure-weighted Poisson deviances, using each resample's exposure total. Source test support below two unique policies, fewer than 40 valid draws, invalid arithmetic, or an unusable percentile interval cause abstention. Finite draws containing only one distinct policy contribute to the distribution and are counted separately. When supported, the 95% interval uses the 2.5th and 97.5th percentiles. The 40-draw requirement is a mechanical tail-resolution floor. Coverage, representativeness, retraining, and future-time uncertainty are outside this test.

An independent scalar oracle used claims `[0,3,1,2]`, exposure `[0.25,2,0.75,1]`, and explicit monetary losses `[0,120,30,90]`. It yielded observed frequency 1.5, predicted frequency 1.46875, weighted MAE 0.09375, and pure premium 60 money units per exposure-year. A separate scalar paired calculation using seed 53 and 200 draws yielded point −0.19441418877956254 and interval [−0.47054551749089885, −0.008233541140112028]. The independent review checked 200 valid draws and 3 single-policy draws and verified abstention when finite draws produce nonfinite or collapsed percentile bounds.

## Resource and verification scope

Source admission caps are 128 MiB and 1,000,000 rows, plus exact CSV/ARFF schema. The snapshot copies at most the admitted bytes to temporary disk with 1 MiB streaming blocks. CSV/ARFF parsing and pandas frame materialization, split copies, SQL grouping, feature transforms, fit, evaluation and figures have separate resource use.

On Windows with CPython 3.13.16, a fresh process acquired and parsed a 3,882,696-byte CSV of 100,000 synthetic rows generated with bounded categorical cardinality, then split and fit all three models on 59,922 rows with HGB `max_iter=5`. Cumulative `PeakWorkingSet64` was 183,926,784 bytes through snapshot/parse, 186,146,816 through split, and 199,020,544 through fit. The probe excluded scoring and rendering. It does not establish an RSS cap, a million-row fit, or identical peaks for wider category cardinality, unusually large fields, sparse ARFF expansion, or the complete pipeline. The earlier 100,000-row ARFF `tracemalloc` measurement used different instrumentation and stages.

Local logs and synthetic files stay in the ignored `reports/runs/20261116-mc1-mc4/` directory. The previous browser report is checked by its SHA and saved figures. Fresh browser execution remains subject to the existing local-report access denial.

| Check | Observed result and evidence |
| --- | --- |
| `python -m pytest -q` from an export of `816e5ed` | 195 passed, exit 0, `baseline-clean-816e5ed.txt`. The exported source was first on `PYTHONPATH` for subprocesses. |
| Pre-fix regressions | `experiment-red.txt` reproduced an original SHA with swapped training rows. `report-red.txt` reproduced missing support and pure-premium notes. `edge-red.txt`, `eda-red.txt`, and `deviance-red.txt` reproduced collapsed bounds, SQL denominator/type or overflow failures, and a nonfinite deviance. `reconciliation-red.txt` reproduced accepted inconsistent predicted totals. Each command exited 1. |
| Focused and independent checks | 103 focused tests passed during integration. The read-only reviewer ran an independently selected 66-test suite and the scalar calculations documented above. |
| Final full suite and lint | 257 passed, exit 0, `full-final.txt`. `ruff check src tests scripts` and `ruff format --check src tests scripts` exited 0. Threads were limited to two for OMP, OpenBLAS, and MKL. |
| `motorclaimlab run` then `render` from synthetic data | 120 analysis rows at 99.50 exposure-years and 300 audit rows at 243.75. Five valid draws yield no interval. Both CLI exits were 0 and all eight renderer artifact hashes matched. Invalid exposure, overflowed JSON number and mismatched source digest each exited 1 before output creation. See `report-offline.txt` and individual CLI logs. |
| Build, dependency check, and installed wheel | `build --no-isolation`, distribution inspection, and `uv pip check` passed. A stale comparison manifest predated a Ruff formatting change and differed on the validator's source digest while all eight artifact hashes already matched. Fresh checkout-source rendering and the installed wheel imported from a separate target outside the checkout matched the complete renderer fingerprint and all eight artifact hashes in `wheel-smoke-final.txt`, exit 0. |
| Preservation | Published historical browser report SHA `58a2f5f71fc64d6db17ba56f0b3ecb0f349f1ae603c6805a39ebd12f0aecd236` and display values 0.626294, 0.605803, 0.574883, paired endpoints −0.05512 and −0.04785, and 13,566 top-bin rows matched the saved evidence. Historical Git-blob guards passed. The new report was checked via HTML structure and saved SVG/PNG artifacts. |
