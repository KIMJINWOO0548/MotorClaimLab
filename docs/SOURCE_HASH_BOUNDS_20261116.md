# Bounded source fingerprints (2026-11-16 KST)

The experiment previously hashed source files before dataset admission, allowing an oversized source to be read despite the parser limit. Fingerprinting now rejects nonregular and oversized sources before reading, reads no more than the configured limit plus one detection byte, and rejects observed metadata changes during hashing. Normal SHA-256 and MD5 results are unchanged.

Path metadata is compared with subsequent path metadata; descriptor metadata is compared with subsequent descriptor metadata. Their identity fields are not compared across APIs because the Windows execution environment reported different identities for unchanged files.

Validation:
- Before the fix: 2 failure demonstrations and 1 ordinary digest test passed.
- Focused final tests: 6 passed, including growth after open, same-size mutation and distinct stable path/descriptor identities.
- Full regression: 190 passed (before adding the sixth focused compatibility test); that additional focused test passed separately.
- Ruff and git diff whitespace checks passed.

These are input-byte and observed-change checks, not a constant RSS promise, an immutable snapshot, or protection against adversarial same-metadata changes. Existing source rehashes around loading/fitting remain in place. No original dataset, frozen historical result, model, main branch or data-rights claim changed.
