# Verification evidence

2026-11-01 KST. Internal AI-assisted implementation/review, not external human or actuarial review.

## Implementation checkpoint

| Check | Actual result |
| --- | --- |
| Full offline pytest suite | **88 passed**, exit 0, 41.73 seconds on Windows / Python 3.12.10 |
| Ruff check / format check | exit 0 |
| Locked dependency consistency (`uv pip check`) | exit 0 |
| Initial wheel / sdist build | exit 0; later changes require final rebuild |
| Distribution contents | 14 wheel / 43 sdist members at that checkpoint; raw data, local runs and environment excluded |
| Pinned raw source | MD5 matched; computed SHA-256 and actual audit in [source-audit.json](evidence/source-audit.json) |
| Actual browser audit | **SKIPPED / DENIED**: file URL protocol blocked; no localhost, alternate browser or indirect workaround attempted |
| GitHub CI | Configured; status must be checked after the implementation push |
| Full real-data model comparison | Pending at this checkpoint; source audit is not performance evidence |

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
