# MotorClaimLab design

2026-11-01 KST. These are implementation decisions made for the user's request to design, build and publish a standalone portfolio project. They are not insurer requirements.

## Purpose and deliverable

Question: after accounting for observed policy duration, where do simple and nonlinear models under- or over-predict automobile insurance claim frequency?

Deliver a Python package, offline CLI, source-audited public-data experiment, SQL EDA, fixed model comparison, error analysis, static HTML/Markdown report, aggregate reproducibility evidence and public Git history. A successful study may find that the complex model does not beat the simpler model. Report observed results without choosing a favorable seed.

## Alternatives and chosen approach

1. Notebook only: low setup cost, but hidden execution state weakens reproducibility.
2. **Package + CLI + standalone HTML report (chosen):** testable data/model boundaries, deterministic runs, no server or cloud, easy interview demonstration.
3. Hosted prediction application: adds credentials, deployment and product claims unrelated to the current research question. Deferred.

No integration or modifications to CaseProof/InsureDataGate are required. A future adapter can consume aggregate artifacts after its contract is separately agreed.

## Data contract

Pinned OpenML 41214 v1 ARFF and published MD5, plus a locally computed SHA-256. Downloads go to ignored `data/raw`. No auto-download in tests or imports. Use HTTPS, bounded timeout/size, reject checksum mismatch and existing target paths. Never publish individual rows, split membership or predictions.

Require 12 fields, unique integer IDpol, finite nonnegative integer ClaimNb, finite positive Exposure and Density, finite nonnegative ages/power, positive BonusMalus and nonempty categorical values. Do not silently correct, clip or deduplicate source rows. Record unusual values. Raw data is immutable; derivations are in memory.

## Frozen experimental protocol

- Seed `20261101`. Deterministic SHA-256 assignment by seed and policy ID: train 60%, validation 20%, test 20%. Assignment is independent of input order and targets. Reject duplicate IDs.
- Optional bounded row sample is selected by a separate hash ordering before split, never by target; label it sampled. Full run remains available.
- Split before any learned preprocessing. Train-only encoders, imputation if ever introduced, scalers and any learned cutpoints. No target-derived predictors. Covariates are VehPower, VehAge, DrivAge, BonusMalus, VehBrand, VehGas, Area, Density, Region.
- Target `ClaimNb / Exposure`, fit weights `Exposure`; predicted count `predicted rate * Exposure`.
- Models: training weighted mean; PoissonRegressor(alpha=1e-4, max_iter=300); HistGradientBoostingRegressor(loss='poisson', max_iter=100, max_leaf_nodes=15, min_samples_leaf=100, learning_rate=0.05, early_stopping=False). Fixed parameters, no grid search.
- GLM: one-hot categories, scaled numeric variables; HGB: ordinal categories explicitly marked categorical, safe unknown handling. Numeric/categorical classification is fixed in source. Exclude IDpol, ClaimNb and Exposure as predictors.
- Select lowest exposure-weighted validation Poisson deviance, ties favor simpler model. Keep all training fits frozen and evaluate on test once. Test outcomes never trigger model changes.
- Thread limit 2 for reproducibility and bounded laptop load. Record dependencies, settings, code digest, source checksum, split sizes/digests, fit times and command.

## Evaluation and interpretation

Primary metric: exposure-weighted mean Poisson deviance of frequencies. Secondary: exposure-weighted frequency MAE, total observed/predicted claims and their ratio. No classification accuracy.

Use ten prediction-ranked groups for calibration and fixed driver-age/vehicle-age/Area segments for exploratory residual analysis. Present counts and exposure with every segment; do not infer causality or fairness certification. Sparse cells must be marked as such. Test segmentation is descriptive, never a threshold optimization step.

Paired policy bootstrap (200 draws by default, fixed seed) compares selected model with mean baseline on test. Store percentile 95% interval of deviance difference; negative favors selected model. This interval is conditional on this split and frozen fits, not uncertainty over retraining or time shifts.

## Modules and interfaces

`src/motorclaimlab/data.py`: fetch_dataset(directory: Path) -> Path; load_dataset(path: Path) -> DataFrame; validate_frame(frame: DataFrame) -> dict; split_frame(frame, seed=20261101) -> dict[str, DataFrame]. `sample_frame(frame, max_rows, seed)` uses a distinct deterministic hash ranking. Raises ValueError on invalid user data.

`models.py`: fit_models(train: DataFrame, seed=20261101, max_iter=100) -> dict[str, object]. Values expose predict(DataFrame) -> positive finite frequency ndarray. Keys in complexity order: mean, poisson_glm, poisson_hgb. Fit preprocessing only on train. Convergence failures are surfaced, not suppressed.

`evaluation.py`: evaluate_predictions(frame, predictions) -> dict; calibration_table(frame, predictions, n_bins=10) -> list[dict]; segment_table(frame, predictions) -> list[dict]; paired_bootstrap(frame, selected_predictions, baseline_predictions, seed=20261101, draws=200) -> dict.

`experiment.py`: run_experiment(input_path: Path, output_dir: Path, seed=20261101, max_rows=None, max_iter=100, bootstrap_draws=200) -> dict. Refuse existing output directory before work, run full audit, sample/split, fit, choose on validation, evaluate test, write aggregates, local split/prediction artifacts, source/code/dependency fingerprints, SQL EDA and report. Local split membership/predictions stay ignored under reports/runs.

`report.py`: render_report(results: dict) -> str standalone escaped HTML, no network resources or JS required; write report.md and chart SVGs from aggregates. CLI: python -m motorclaimlab fetch --output data/raw; run --input PATH --output NEW_DIR [--max-rows N] [--max-iter N] [--bootstrap-draws N]. Nonzero exit for invalid input/output.

`eda.py`: summarize_sql(frame) -> dict via disposable in-memory SQLite; claim/exposure aggregations, not averages of per-row rates. Only aggregate outputs persist publicly.

## Validation and publication

TDD tests cover invalid/nonfinite data, duplicate IDs, stable disjoint split, unknown categories and held-out preprocessing, weighted metrics against hand-derived examples, baseline exposure weighting, model fit/predict, bootstrap pairing, output overwrite refusal, HTML escaping and actual CLI execution with a clearly synthetic fixture. Online download/full experiment is a separate check.

Execution ruling: the actual source's STRING attributes require liac-arff rather than SciPy's limited ARFF reader. Gzip transport is decoded with a size bound before checksum verification. Browser use was explicitly denied by the URL policy; actual browser desktop/mobile checks are SKIPPED and no alternate server/surface is used. Offline HTML/SVG checks and genuine Matplotlib PNG inspection provide the allowed visual evidence.

Public milestones: design/contract; tested data validation and evaluation; tested models/CLI/report; curated public-data results and verification. Each push is a normal forward push. User has explicitly authorized public GitHub creation and periodic commits/pushes; no deployment or paid services are in scope. All staged files must pass a secret/PII/raw-data review.

## Limits

Historical French data, unresolved original source provenance, no observation dates, no severity/claim cost model, no causal effect or economic impact measurement, no insurer validation or human actuarial review, no production decisions. No performance threshold is predeclared as a completion requirement; honest comparison and reproducibility are the acceptance criteria.
