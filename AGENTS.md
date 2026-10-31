# MotorClaimLab contributor contract

- Read README.md, docs/DESIGN.md, docs/STATUS.md and docs/DATA_SOURCE.md first.
- This is a historical educational insurance frequency study, not a pricing, underwriting or claim decision service. Never claim KB endorsement, measured business savings, current Korean validity or external expert review.
- Preserve raw data. Dataset downloads, per-policy records, predictions, identifiers and fitted binary models stay ignored. Publish original code, attribution, source hashes and aggregate results only.
- Never install new packages, plugins or MCP servers without user authorization. The user has authorized this project's public GitHub repository and incremental commits/pushes. That does not authorize deployment or production access.
- Write independent behavior tests first, observe RED, implement, run affected tests and full suite. Never change expected answers to match outputs.
- Keep model selection on validation data; test data must not set preprocessing, hyperparameters, model choice or business thresholds. Fit preprocessing on training data only.
- Frequency is ClaimNb / Exposure; fit and evaluate using Exposure weights. Do not use IDpol, ClaimNb, Exposure or derived target values as covariates.
- No silent clipping, deduplication or removal of positive-exposure source rows. Reject invalid schema; audit unusual but valid observations.
- Record exact commands, versions, exit codes, source/code hashes and limitations in new reports/runs directories. Curated docs/evidence contains aggregates and sanitized evidence only.
- Do not overwrite existing output directories. Use temporary test directories. No arbitrary database/file deletion, no secrets in logs, no force pushes.
- Use a modular Python package and offline static reports. No web server, LLM, external inference or cloud infrastructure is required.
- Internal AI review is not independent human or actuarial review. Update status only after checks actually run.
