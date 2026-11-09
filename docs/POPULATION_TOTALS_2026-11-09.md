# Input audit and split-total integrity

2026-11-09 UTC. Independent change from accessible remote
`improve/competitive-depth-20261106`, base
`69e0e85582530f77a99928beeb2ea09c8576ce3e`, on
`improve/exposure-total-integrity-20261109`. Inaccessible preservation files were
not read or restored; this is a separate history from those prior changes.

## Corrected boundary

`validate_frame` previously summed individually valid integer ClaimNb values in
binary64 and converted the rounded result to int. The exact synthetic total
`2**53 + 1` could become `2**53`. Partition summaries separately used fixed-width
pandas integer accumulation, which could wrap when the total exceeded int64.
Individually finite positive Exposure values could also produce an infinite
audit total instead of a clear validation error.

Validated per-row counts now accumulate as Python integers. Exposure uses
`math.fsum`, preserving small positive contributions where representable, and
rejects overflow/nonfinite totals with `ValueError("Exposure total must be finite")`.
Partition metadata reuses the same validated rows/claims/exposure aggregates.
The existing per-row numeric range and schema requirements are unchanged. No
observations are clipped, deduplicated or removed, and inputs are not rewritten.

Full-input audit and sampled-population split totals retain their separate
meanings. Sampling, policy hash split, membership ordering/hash, training inputs,
validation selection, metrics definitions and renderer/UI source are unchanged.
No frozen experiment or published presentation was regenerated.

## Actual verification

Linux / Python 3.12.14, project-only virtual environment. Necessary dependency
installation was already authorized by the user; the repository's
`requirements-dev.lock` was installed from official PyPI with `--require-hashes`.
No system package or global setting was changed. Exact versions, commands,
exit codes and log hashes are recorded in the evidence.

| Check | Observed result |
| --- | --- |
| Accessible-base baseline | 167 pytest cases passed, exit 0 |
| Independent new RED | Ten cases: eight failed, two passed, exit 1; two numeric RuntimeWarnings from the old overflow path |
| Affected GREEN | 53 cases passed, exit 0 |
| Full regression | 177 cases passed, exit 0; no skipped cases |
| Lint / format / dependencies | Ruff check, format check and pip check all exit 0 |
| Historical evidence | Original Git-blob evidence and presentation checker pinned to renderer `6efb433791c012e273ef12a6a6fcb28dfd525b51` both exit 0 |
| Packaging | Wheel/sdist build with `--no-isolation` and distribution member checks exit 0; no package publication |
| Preservation | All 63 existing tracked evidence files and eight protected runtime/config files are byte-identical to base, including renderer, models, evaluation, EDA and dependency locks |
| Internal read-only review | Two internal agents found no blocking correctness regression; not external human or actuarial review |

The new cases cover exact sums beyond binary64's consecutive-integer range and
int64, ordinary zero claims/large finite exposure, small exposure contributions,
overflow without a numeric warning, failure before fitting/output creation,
whole/sampled partition totals and source/frame preservation. The large-count
orchestration cases deliberately stub model fitting, SQLite EDA and rendering to
isolate metadata production; they are not large-count model-accuracy tests.
Existing real synthetic fitting/workflow tests ran in the affected/full suites.

Actual synthetic CLI execution uses a 300-row full input and 180-row selected
population, verifies their separate claim/exposure totals and existing-output
refusal, and rejects overflowing exposure before creating output. The first
controller attempt omitted its own module search path after the normal CLI
returned zero; it failed with ModuleNotFoundError and is retained as a failed
controller attempt. The corrected controller used a fresh temporary directory.
No application change was made to resolve that controller error.

An extra packaging-controller assertion also failed because it expected JSON
evidence inside the source archive. The existing MANIFEST includes Markdown
documentation and tests, and provides JSON evidence through Git instead. Build,
the repository distribution-member checker and runtime wheel/source comparison
had passed. The package contract was preserved and the final controller checks
that actual contract; no runtime or MANIFEST change was made for this assertion.

Observed full audit: 300 rows, 200 claims, 200 exposure-years. Observed selected
population: 180 rows, 125 claims, 120.25 exposure-years. The corrected normal CLI
returned 0; overflowing exposure returned 1 and left its output path absent.

Curated aggregate-only evidence is
[verification.json](evidence/population-totals-20261109/verification.json) in Git;
like historical JSON evidence, it is omitted from the source archive by the
existing Markdown-only documentation rule. The focused guide and tests are
included in the archive.
Detailed local logs stay ignored under
`reports/runs/20261109T161703Z-0e408681-population-totals/`. Temporary synthetic
policy files and predictions are not published. Commit/push and remote SHA/CI
observations are recorded separately after verification.

## Limits

This improves input audit and split metadata, not every numerical operation in
the pipeline. Evaluation still uses binary64 metrics; SQLite SUM retains its
fixed-width limits; rendering arbitrary-size integers and full-pipeline extreme
values are not newly guaranteed. Exposure remains binary64, not exact decimal
arithmetic, and separately rounded partition totals can differ slightly from a
whole-population sum. No speedup is claimed for the additional split validation.

No full public-data retraining, download, new browser session, Windows or other
Python version was run for this increment. Historical results remain historical.
No current clinical, Korean insurance, operational, pricing, underwriting,
claim-decision, fairness or business-impact accuracy is established. Remote CI
success is not implied by local checks or older CI records.
