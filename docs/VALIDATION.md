# Verification evidence

## Audit and split-total increment — 2026-11-09 UTC

The accessible remote-base suite passed 167 cases. Ten new synthetic boundary
cases reproduced eight failures; after the audit/partition correction, the
affected suite passed 53 cases and the full suite passed 177. No prior expected
answers or frozen results were changed. This is a separate implementation from
inaccessible preservation files, with no UI update or actual-data rerun.
Exact scope, commands, observed controller failure, successful checks and limits
are recorded in [POPULATION_TOTALS_2026-11-09.md](POPULATION_TOTALS_2026-11-09.md)
and its linked aggregate-only evidence. Historical checks below remain distinct.

2026-11-01 KST. Internal AI-assisted implementation/review, not external human or actuarial review.

## Implementation checkpoint

| Check | Actual result |
| --- | --- |
| Full offline pytest suite | **88 passed**, exit 0, 41.73 seconds on Windows / Python 3.12.10 |
| Ruff check / format check | exit 0 |
| Locked dependency consistency (`uv pip check`) | exit 0 |
| Final implementation wheel / sdist build | exit 0 |
| Distribution contents | Final publication rebuild: 14 wheel / 49 sdist members; raw data, local runs and environment excluded |
| Pinned raw source | MD5 matched; computed SHA-256 and actual audit in [source-audit.json](evidence/source-audit.json) |
| Actual browser audit | **SKIPPED / DENIED**: file URL protocol blocked; no localhost, alternate browser or indirect workaround attempted |
| GitHub CI | **All three jobs success** for 751e6f7: Linux 3.12/3.13, Windows 3.12; [run 41218810116](https://github.com/KIMJINWOO0548/MotorClaimLab/actions/runs/41218810116) |
| Full real-data model comparison | **exit 0**, 678,013 rows; [actual aggregate results](evidence/benchmark/results.json) |
| Isolated wheel smoke | **exit 0**; separate hash-locked runtime, package imported from site-packages; outside-checkout 300-row synthetic CLI |
| Final online fetch CLI | **exit 0**; fresh ignored output; decoded bytes match pinned MD5 |
| Offline visual check | Actual two Matplotlib PNG charts inspected; no browser rendering/accessibility claim |

Local commands:

```text
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
uv pip check --python .venv/Scripts/python.exe
python -m build --no-isolation
python scripts/check_distribution.py
```

The full test command uses only hand-authored synthetic observations and does not download data. Its passing result does not establish future-period or current Korean insurance performance.

## Observed RED and recovery evidence

- New data, evaluation, model and orchestration modules first failed because the requested implementation was absent.
- Boolean numeric source values: **11 failed → 11 passed**; reject Python and NumPy booleans before numeric coercion. External read-only reproduction supplied the initial finding; no original project files were edited.
- Calibration bins: **1 failed → passed**; numeric order replaces `1,10,2,...` lexical order.
- Report boundaries: **4 failed → passed**; lowercase SQL Area labels, one EDA table, per-row sparse flags and unverified local-source wording.
- Integer exposure SQL arithmetic: **1 failed → passed**; floating division in overall and Area aggregations. Independently reproduced by internal reviewer and read-only coordinator.
- Source ARFF STRING: **1 failed → passed**; SciPy's parser does not support that actual source attribute type, so the package uses the MIT-licensed liac-arff parser.
- Gzip transport: **1 failed → passed**; verify the decoded original bytes against pinned source checksum.
- Offline PNG exports: **1 failed → passed**; real Matplotlib PNG charts supplement SVGs without a browser.

Initial uncompressed Python download was manually stopped after prolonged transfer without progress output. A curl attempt timed out at 120 seconds (exit 28; 11,180,737 bytes). Range resume was unsupported (exit 33). A compressed transfer then completed (exit 0; 6,999,116 transferred bytes; 69.020322 seconds), yielding **36,288,567 decoded bytes** with the exact pinned MD5. These are download outcomes, not model timings.

Full local logs remain in ignored `reports/runs/bootstrap/` and `reports/runs/boolean-boundary/`. Public evidence publishes aggregates and sanitized summaries, never contract rows or per-policy predictions. No expert score, business saving or operational result is claimed.

The first isolated-wheel smoke controller failed decoding a Korean Windows path from the child process. No application study had executed in that attempt. The same wheel was then run with an explicitly UTF-8 child process and completed successfully; no model code or expected results were changed.

Git Credential Manager stalled during the implementation push; only the owned push process tree was stopped. A per-command existing GitHub CLI credential helper completed the normal forward push. No token, global Git configuration or credential store was changed.

After the aggregate publication, verification against actual Git blobs found **five** artifact hash mismatches caused by Git's line-ending normalization. The original generated bytes and expected hashes were retained. Evidence paths now disable text normalization, and legal Matplotlib path whitespace is explicitly identified in repository attributes. `python scripts/check_evidence.py --staged` then verified **all ten** manifest-listed Git blobs, exit 0. The same hash check is included in CI. It authenticates byte identity only, not authorship, data rights or scientific correctness.

The integrity fix `dda7b54054d38ad652bfa5a7103c9b1515102695` passed [CI run 41219758581](https://github.com/KIMJINWOO0548/MotorClaimLab/actions/runs/41219758581), including the actual Git-blob hash check. Local HEAD and remote main were both that SHA with a clean working tree at the publication checkpoint. Subsequent closure documentation changes do not alter analysis code or the original study artifacts.
