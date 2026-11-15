# Saved JSON integrity (2026-11-16)

The presentation reader accepted duplicate JSON keys in both frozen results and
selection records. A conflicting selected_model was silently discarded by the
JSON parser, so the resulting provenance referred to ambiguous input bytes.
The reader now rejects duplicate keys at any object depth before creating the
output directory. The error contains no input key/value. Existing incomplete
aggregate rendering, model selection and historical results are unchanged.

Before implementation: both independent duplicate-key regressions failed (the
renderer created presentations instead of rejecting). After: focused 4/4 pass
including nested duplicates and error redaction. Full pytest: 193 passed.
Ruff check and format of changed Python files passed after import ordering fix.
These synthetic aggregate tests do not establish real-data accuracy or source
rights, and this change does not introduce exhaustive schema validation.
