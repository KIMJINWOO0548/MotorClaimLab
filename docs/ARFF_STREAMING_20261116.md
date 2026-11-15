# ARFF admission streaming (2026-11-16)

The 128 MiB input and 1,000,000-row population contracts remain unchanged.
ARFF headers are checked before row consumption. The existing liac-arff parser
now yields rows lazily; at most 10,000 Python row lists are converted per chunk.
An input exceeding the row cap is rejected after at most cap+1 parsed rows,
without returning a truncated population. Nominal and STRING values retain the
existing parser semantics and all existing numeric/schema validation remains.

This reduces duplicate Python row-list storage; it is NOT a constant-memory
pipeline or an RSS cap. Chunk frames and the concatenated frame overlap, and
validation/model training allocate further arrays. Large fields and headers are
still bounded only by the input byte admission limit. Concurrent source changes,
ARFF sparse expansion, model fitting peak memory and the full million-row limit
remain separate validation work. No raw policy data or historical model results
were altered.

## Synthetic measurement

Windows Python 3.13.16, 100,000 synthetic rows, 3,789,248-byte ARFF:
- Previous eager parse + frame construction: tracemalloc peak 81,525,600 bytes,
  4.378 seconds.
- New chunked load INCLUDING validation: peak 32,194,075 bytes, 7.000 seconds.
- Both returned 100,000 rows and frame deep size 26,900,132 bytes.

These stages differ, so the times are not a speed comparison. tracemalloc is
Python-tracked allocation, not process peak RSS or total native memory. Script
and aggregate measurement remain in local reports/runs/arff-streaming-20261116.

## Verification

Two independent tests failed before implementation and passed afterward:
row-limit lazy consumption and header rejection before row parsing. Real ARFF
nominal/STRING compatibility, trailing-malformed oversize rejection and a
10,200-row multi-chunk content check are covered. Focused initial run: 23 passed.
Full first run: 184 passed / 1 failed because subprocess CLI could not import
uninstalled local package. This is retained, not represented as a product pass.
Final installed full run and publication are recorded separately.

Final run after normal local editable installation: **185/185 passed** in 58.29s, exit 0. Ruff check and format check passed. Independent review reran the four ARFF tests: **4/4 passed**, no scoped blocking issue. Full-suite initial failures and install errors remain in local logs. No true RSS bound, full million-row experiment, new historical-data study or remote CI pass is claimed.
