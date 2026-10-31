# Renderer 3.0 verification

2026-11-01 KST. Repository: https://github.com/KIMJINWOO0548/MotorClaimLab, branch `main`. Baseline: `d1ceb97079462c5e36f2de13028008fe4a1acbf3`.

The user requested a more expressive, original contemporary UI. The change uses a petrol/coral chart-led opening, an original lane mark, large Korean title, horizontal model comparisons and light analytical tables. It changes no experiment values or selection. Eight new outputs and renderer source hashes are in `docs/evidence/presentation-v3/presentation.json`.

## Observed checks

| Command / check | Actual outcome |
| --- | --- |
| `python -m pytest tests/test_visual_report.py -q` before implementation | **RED**, exit 1: two missing visual-opening/theme regressions; independent contrast calculation passed |
| Affected report/presentation/integrity tests after implementation | 28 passed, exit 0 |
| Initial complete suite | 107 passed, exit 0 |
| Independent offline review | Reproduced missing-calibration warning overlapping legend; no source changes by reviewer |
| New warning-position regression before fix | **RED**, 1 failed, exit 1; SVG y positions demonstrated overlap |
| `python -m pytest tests/test_visual_report.py tests/test_report.py tests/test_presentation.py tests/test_presentation_integrity.py -q` after fix | **29 passed**, exit 0 |
| `python -m pytest -q` after fix, process-local OMP/OpenBLAS/MKL thread limit 2 | **108 passed**, exit 0, 23.41 seconds |
| `python -m ruff check src tests scripts`; `python -m ruff format --check src tests scripts` | Both exit 0; 22 formatted files |
| `python -m motorclaimlab render --results docs/evidence/benchmark/results.json --selection docs/evidence/benchmark/selection.json --output docs/evidence/presentation-v3` | Exit 0; renderer 3.0, model_execution=false; eight artifacts |
| Frozen prior-file preservation | 21 Git-tracked original/v2 evidence files match baseline bytes; original ten expected hashes unchanged |
| `python -m build --no-isolation`; `python scripts/check_distribution.py` | Exit 0; wheel/sdist built; local/raw data excluded |
| Fresh project-only wheel environment, hash-locked runtime dependencies, built wheel installation | Exit 0; no global package/config changes |
| Wheel `python -I -X utf8 -m motorclaimlab render ...`, cwd in a fresh OS temporary directory outside checkout | Exit 0; import from site-packages; same renderer fingerprint and all eight output hashes as publication; both input bytes preserved |
| Original/current presentation Git-blob checks before publication | Run against staged blobs; outcomes recorded in verification JSON and CI |

The first wheel probe successfully rendered, then its auxiliary import-path check decoded a Windows legacy-code-page path as UTF-8 and failed. The probe was corrected to use explicit `-X utf8` for that subprocess and rerun successfully. No product code or expected data was changed for this harness correction.

## Visual evidence and tools

Actual generated Matplotlib PNGs for calibration, model comparison and paired difference were inspected. The incomplete-calibration fixture was inspected again after moving its warning to separately allocated figure-title space. Visible endpoint values, actual rank ordering, distinguishable solid-circle/dashed-square cues and zero reference are retained. Full calibration numbers remain in the HTML table. The dark chart's text and series colors exceed 4.5:1 against its background in an independent WCAG luminance calculation.

UI/UX Pro Max design-system queries and one narrower retry, Frontend Design, Uncodixfy and Ponytail decisions; official F1/Stripe/Observable research; connected Context7 Matplotlib lookup; GitHub MCP historical manifest read; actual routed Luna/high research and Sol/medium review are recorded in [UI_VISUAL_REFERENCES.md](UI_VISUAL_REFERENCES.md). No copied assets, remote fonts, JS framework, cloud service or extra dependency. No live-model execution or retraining occurred.

Local detailed logs and wheel probe: `reports/runs/20261031T174310Z-visual-v3/`. Curated machine-readable results: `docs/evidence/presentation-v3-verification.json`. Current renderer SHA-256: `04ba99e12b1ef5aa6ec65459e06ac8445017c8a0252ff64706990d784b2dbd81`.

## Unrun and limits

Actual HTML browser layout, responsive viewports, keyboard/screen-reader interaction, browser print behavior and animation perception remain **SKIPPED / DENIED** by the earlier file-URL security policy. No local server, alternate browser surface or CDP workaround was used. Responsive, skip-link, focus, print and reduced-motion rules are present and structurally checked, not claimed as live-browser validation. Source website images could not be freshly inspected through the allowed web image tool; official source research is text-based and no visual-clone claim is made.

Internal AI-assisted review is not external human, actuarial or insurer review. Historical French data and a fixed split do not establish current Korean applicability, temporal generalization, pricing/underwriting/claim-decision fitness or measured business effects.

## Observed publication CI

Implementation commit `7323b70939642a80e0f71bc61474aad58838a62e` was pushed to `main`. Actual [CI run 41226676309](https://github.com/KIMJINWOO0548/MotorClaimLab/actions/runs/41226676309) completed **success** on all three jobs: Ubuntu Python 3.12, Ubuntu Python 3.13 and Windows Python 3.12. Their lint, original/current Git-blob hashes, behavior tests, wheel/sdist builds and local-data exclusion steps passed. Existing GitHub action runtime/runner migration notices were warnings, not failed checks.

`uv pip check --python .venv/Scripts/python.exe` also passed for all 32 installed packages. An optional `python -m pip check` attempt could not run because this uv-created environment contains no pip module; the installed uv checker provided the dependency check without adding a package.
