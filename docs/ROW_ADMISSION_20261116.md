# Source row admission (2026-11-16 KST)

Supported source size is at most 1,000,000 rows and 128 MiB. This includes the
historical 678,013-row dataset. CSV reads at most limit+1 rows then rejects the
whole input if oversized; it never silently samples or reports a truncated
population. Frame validation also rejects oversized ARFF/in-memory results.
ARFF still parses the size-limited file before validating row count; this is not
a streaming or universal peak-memory guarantee. No dataset or model changed.

Two new boundary tests failed before implementation and passed afterwards.
Admission tests: 4/4. Full Windows Python 3.13.16 pytest: 181/181 in 58.31 seconds,
exit 0, with source PYTHONPATH for CLI subprocesses. Changed-file Ruff passes.
