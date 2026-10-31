# Saved-result reading flow: audit comparison and 3.1 closure

2026-11-01 KST. This follows the user's resumed request and the supplied `VISUAL_REDESIGN_AUDIT.md` (v2 PNG/source review, not a v3 browser audit). Baseline is `a736031cda69f39deeecf00cdab2a9299ba495d5`. No duplicate redesign or model work was started.

| Concrete observation in supplied review | Current evidence and bounded resolution |
| --- | --- |
| Uniform white document; weak visual opening | Already changed in v3: petrol/coral chart-led opening, original lane mark, large Korean heading and light analytical content. Source implementation and PNG color treatment exist; perceived beauty and actual viewport composition are not certified. |
| Broad bars and unclear selection context | V3 uses horizontal zero-origin bars plus an exact three-model table. 3.1 adds a validation-selection note to the standalone figure. Validation/test deviance and weighted MAE are simultaneously visible; a metric switch would hide already comparable values, so none was added. |
| Twenty point labels; unclear series and distant support | V3 reduced labels to endpoints. 3.1 names Observed/Predicted at the right endpoints and reserves right-side space. The same figure includes highest-rank bin support and stored claim totals: bin 10, 13,566 rows, 4,895.67 exposure-years, 1,831.00 observed / 1,615.58 predicted claims. All ten exact rows remain in the native table. No bin confidence band or new subgroup statistic. |
| Standalone interval omits model identities and 95% level | 3.1 PNG/SVG title names Poisson HGB − Training mean, 95% paired bootstrap interval, frozen fits and split. Zero and original bounds remain. HTML/Markdown also name the comparison; explanatory text excludes retraining/time-shift uncertainty. |
| Thirteen rows in one table; mostly scrolling | 3.1 uses three native, initially open dimension disclosures: driver age 4, vehicle age 3, Area 6. Every saved row retains support, deviance, MAE, observed/predicted counts, ratio and Sparse status. Unknown dimensions remain visible in a fallback disclosure; `<25`/`<5` and unknown labels are escaped. |
| Interpretation and actual supported exploration | Question → all three model results/validation choice → named conditional interval → ten calibration bins → dimension-specific saved segment tables → source/limits. Ratio >1 means underprediction, <1 overprediction; absent ratios stay N/A. The interface states that segments exist for the selected model only and are descriptive. |

This is a bounded alternative to the review's proposed sortable/selector workspace. No sortable-table, bin-click inspector or dynamic metric selector is claimed. All saved model metrics are already displayed, and only 13 predeclared segment rows exist. Native disclosures and the complete exact tables support the current reading task without JavaScript or a new dependency. Arbitrary intersections, per-model segment comparisons, per-policy records, causal explanation, extra statistics and refitting remain outside the saved evidence.

## Preservation and validation

New outputs go to `docs/evidence/presentation-v3-1/`, renderer **3.1**, using the same original results/selection. Original ten experiment artifacts/expected hashes, v2, v3 and their manifests remain byte-identical. The current Git-blob guard advances to the new derivative; historical sources stay traceable through their unchanged manifests and Git history.

Four independent flow regressions first failed (exit 1). They cover standalone comparison context, numerical highest-bin support with repeated bins, missing-support N/A, and native dimension navigation preserving unknown rows/escaping. Affected suite initially passed 33 tests; full suite initially passed 112. A formatting check caught one 101-character test line after the output path changed; formatting fixed it without source/evidence changes. Final full-suite, wheel, hashes and actual CI outcomes are recorded in `docs/evidence/presentation-v3-1-verification.json` after execution.

Actual final Matplotlib calibration and paired-interval PNGs were inspected. This observed legible support text, separated endpoint labels, explicit identities/95% and retained zero; these images are not screenshots of the HTML page. Offline parsing verifies 3 model rows, 10 bins, 4/3/6 saved segment rows and native links/disclosures. Wheel execution uses an isolated installation outside the checkout and never trains a model.

UI/UX Pro Max focused query `disclosure table navigation --domain ux -n 3` returned Responsive/Table Handling, Sticky Navigation and Keyboard Navigation. Adopted the existing horizontally scrollable labelled tables and native keyboard-operable disclosures/focus treatment; no sticky rail or custom tab-order control. This was a focused accessibility/navigation reference, not a full page template match. Auto Model Router actually dispatched Sol/medium for the independent read-only audit comparison; the coordinator kept its model.

Context7 actually queried Matplotlib [Figure.supxlabel](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.supxlabel.html) and [multiline labels with constrained layout](https://matplotlib.org/stable/gallery/text_labels_and_annotations/multiline.html). The existing constrained-layout figures allocate room for the two-line support label via `supxlabel`; actual generated PNG inspection complements the documented API behavior.

## Remaining verification boundary

No CUA/Chrome/browser UI operation occurred. Screen control remains assigned to the supervisor, and the earlier file-URL policy denial still forbids server/alternate-surface/raw-CDP workarounds. A real page capture and viewport/keyboard/assistive-technology/print inspection remain needed to assess actual rendered flow and aesthetic quality. They are **SKIPPED/DENIED**, not inferred from a test count, PNG or self-rating. No aesthetic score, external human review or current insurance applicability is asserted.
