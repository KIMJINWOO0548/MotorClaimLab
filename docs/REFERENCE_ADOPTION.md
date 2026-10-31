# Report reference adoption

Updated 2026-11-01. This note records upstream patterns considered for the offline report. References informed design choices; no upstream source code, asset, logo, package, service, or result number is copied into MotorClaimLab.

## Sources and bounded application

| Reference (primary source) | Verified license | Useful pattern | Actual local application | Rejected parts and reason |
| --- | --- | --- | --- | --- |
| [MLflow Tracking UI](https://mlflow.org/docs/latest/ml/tracking/) and [dataset context](https://mlflow.org/docs/latest/ml/dataset/) | [Apache-2.0, `mlflow/mlflow` `LICENSE.txt`](https://github.com/mlflow/mlflow/blob/master/LICENSE.txt), blob `db7cb10b5e330d56b40370bc178974ccabe71458` | Dense model comparison with readable numeric columns and adjacent source, run, and dataset context. | `src/motorclaimlab/report.py` comparison rendering: keep the three models together, show the mean baseline, mark the validation-selected model in text, and expose run provenance. `src/motorclaimlab/presentation.py:render_saved` now writes saved-result presentations to the separate `docs/evidence/presentation-v2/` directory. | No tracking server, MLflow dependency, registry, auto-logging, React migration, copied logo/assets, or unnecessary sidebar/search controls. Three frozen models do not need tracking infrastructure or application navigation. |
| [Evidently reports](https://docs.evidentlyai.com/docs/library/report), [conditional tests](https://docs.evidentlyai.com/docs/library/tests), and [output formats](https://docs.evidentlyai.com/docs/library/output_formats) | [Apache-2.0, `evidentlyai/evidently` `LICENSE`](https://github.com/evidentlyai/evidently/blob/main/LICENSE), blob `f339cc7fc8fe13467e1b3f3a7afa02b29714b2bb` | Keep measured metric values distinct from threshold-based checks; standalone report output is useful without a monitoring platform. | `src/motorclaimlab/report.py` and `src/motorclaimlab/presentation.py`: explain metrics and local data/provenance alongside the comparison, with clear interpretation limits. | No Evidently package/cloud/monitoring service, LLM judge, invented default thresholds, green approval/compliance badge, or claim that a metric is a pass status. This offline study has no operational thresholds or external review that would justify those states. |
| [scikit-learn Poisson frequency example](https://scikit-learn.org/stable/auto_examples/linear_model/plot_poisson_regression_non_normal_loss.html) | [BSD-3-Clause, `scikit-learn/scikit-learn` `COPYING`](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING), blob `3d7ee432c15b685eaa654b6abe8f8e3ea8126a8d` | Exposure-weighted frequency metrics and prediction-ranked observed/predicted calibration are interpretable insurance diagnostics. | `src/motorclaimlab/report.py` and `src/motorclaimlab/presentation.py`: retain numeric prediction-bin order, observed/predicted labels, counts and exposure, and describe frequency as claims per exposure-year. Existing evaluation arithmetic remains the source of values. | No copied example values, classification-accuracy headline, refit or metric change for display, or claim that the example established a source-row clipping rule. Tutorial corrections/numbers would change the frozen local contract and cannot substitute for our own measurements. |

The license names and blob SHAs above were checked by reading the three primary repository license files with the connected GitHub MCP `github_fetch_file` tool. Their terms apply if upstream material is redistributed; this change adopts presentation ideas only and does not copy upstream code or assets.

## Applied implementation and local evidence

- MLflow pattern: `report.py:_comparison_table` keeps all three models, the baseline, validation and test columns together, with a textual validation-selected row. `_provenance` uses native `details` for complete source/code/git/seed/split/settings/environment records. The old hero/card grid is removed.
- Evidently pattern: `report.py:render_report` separates measured values from recorded input/processing conditions, uses strict boolean source identity, preserves Sparse flags, and labels missing intervals or calibration totals as unavailable. It adds no approval badge or unconfigured threshold.
- scikit-learn method: `report.py:_figures/_calibration_table` retains stored counts/exposure and numeric bin order, with observed solid-circle and predicted dashed-square cues. No fitting or metric formula changes occur.
- Paired uncertainty: `report.py:_uncertainty_svg/write_uncertainty` draws only the stored selected-minus-baseline interval, an explicit zero line and endpoint/point labels, with fixed-fit/split limitations and a table/text alternative. It is not a per-model confidence bar.
- Versioned derivative: `presentation.py:render_saved`, CLI `render` in `__main__.py`, and `scripts/check_presentation.py` link unchanged saved inputs to renderer 2.0 source hashes and eight derived output hashes. Original ten artifact expected hashes and the original experiment results/selection are preserved.
- Actual local verification: 104 full-suite tests passed; original ten Git-blob hashes passed. The paired interval and calibration were inspected as real offline Matplotlib PNGs. The separate publication/wheel/CI outcome is recorded in the presentation verification note, not inferred from these source references.

## Actual UI/UX Pro Max and Context7 work

The implementation owner read the installed UI/UX Pro Max SKILL.md and ran focused searches:

| Query / domain | Verified result | Application decision |
| --- | --- | --- |
| `confidence interval zero baseline` / chart | Time-Series Forecast / confidence band | Rejected: this report has no date axis or forecast horizon. |
| One retry, `scalar uncertainty interval comparison` / chart | Multi-Variable Comparison / radar; secondary time-series result | Radar and forecast band rejected; no exact paired-interval match claimed. Retained the record's precision caveat, direct labels and line/marker alternatives to color. |
| `table comparison disclosure` / ux | Responsive / Table Handling | Adopted horizontally scrollable native tables and focusable labelled regions; no card conversion. |

All three commands exited 0; their outputs remain in the ignored presentation run directory. The paired interval is an original rendering of stored statistics rather than a claimed skill-prescribed chart type.

Context7 actually resolved Matplotlib and queried `Axes.hlines`, `Axes.axvline`, SVG metadata and reproducibility. Primary API references: [hlines](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.hlines.html), [axvline](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.axvline.html), [SVG output](https://matplotlib.org/stable/api/backend_svg_api.html), [reproducibility and ID collision caveat](https://matplotlib.org/stable/release/prev_whats_new/whats_new_2.1.0.html). Applied in `_uncertainty_svg`, `_figure_svg` and `_inline_svg`: explicit zero in data coordinates, deterministic SVG salt/date handling, and separate inline ID namespaces. No source code or long documentation passages were copied.

## Visual and review limits

The [official MLflow model-table reference image](https://mlflow.org/docs/latest/assets/images/tracking-models-ui-0f88d40c517e103cdead462aab12781a.png) was observed by the research supervisor and is labeled **MLflow 3.0.0rc3**. The observed cues were grouped attributes, readable numeric columns, thin row separators, and a restrained selected state. This records the supervisor's observation; it is not a fresh visual audit by this author or a current-version UI claim. Evidently and scikit-learn primary-document observations are inherited from the supplied research plan; their repository licenses were rechecked through GitHub MCP. Their live applications were not visually audited by this implementation owner.

An earlier UI/UX Pro Max chart search was performed in the companion research task: the first result was rejected as time-series-specific, and one narrower retry returned a radar-chart pattern that was rejected for precise unlike-unit model comparison. No exact scalar paired-interval chart pattern was found. The implemented interval is therefore a project-specific rendering of existing saved statistics, not an upstream design claim. Browser restrictions were respected; this note does not claim a fresh MotorClaimLab browser or accessibility audit.

These are internal AI-assisted reference notes, not independent human, actuarial, or insurer review. The project remains a historical French frequency study, not a pricing, underwriting, claim decision, or production tool.
