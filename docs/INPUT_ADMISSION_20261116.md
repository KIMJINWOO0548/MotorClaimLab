# Local source admission (2026-11-16 KST)

Based on fetched remote e08769e; original clean local checkout 69e0e85 preserved.
Local CSV/ARFF files over 128 MiB now fail before parser invocation. In-memory
frames with duplicate column names receive an explicit schema error rather than
an ambiguous pandas truth-value exception. Original data is never modified.

Tests use synthetic temporary files and frames. Both independent regression tests
failed before the change and passed after it. This admission check is not a
streaming parser or a guarantee against concurrently growing files. Row limits,
parser memory expansion and real-data accuracy remain separate work.

Ruff check and format check pass on the changed source/test. Full pytest is running separately; it is not yet claimed as passed.
