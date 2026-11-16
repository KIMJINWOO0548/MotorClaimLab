"""Aggregate frequency evaluation for frozen predictions on observed policies."""

import math

import numpy as np

from .data import validate_frame

BOOTSTRAP_CONFIDENCE_LEVEL = 0.95
# A 2.5% tail needs at least 40 draws to represent one draw per tail.
BOOTSTRAP_MIN_VALID_DRAWS = 40
BOOTSTRAP_MIN_POLICIES = 2


def _inputs(frame, predictions):
    validate_frame(frame)
    try:
        values = np.asarray(predictions, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Predictions must be numeric rates") from exc
    if values.ndim != 1 or len(values) != len(frame):
        raise ValueError("Predictions must contain one rate per policy")
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("Predicted rates must be positive and finite")
    counts = frame["ClaimNb"].to_numpy(dtype=float)
    exposure = frame["Exposure"].to_numpy(dtype=float)
    rates = counts / exposure
    if not np.all(np.isfinite(rates)):
        raise ValueError("Observed frequencies must be finite")
    return counts, exposure, values


def _metrics(counts, exposure, predictions):
    rates = counts / exposure
    observed = sum(map(int, counts))
    total_exposure = float(math.fsum(exposure))
    with np.errstate(over="ignore", invalid="ignore"):
        expected = exposure * predictions
    if not np.all(np.isfinite(expected)):
        raise ValueError("Predicted claim counts must be finite")
    positive = counts > 0
    # In count units, the exposure-weighted deviance avoids division of extreme rates.
    deviance = expected.copy()
    deviance[positive] += counts[positive] * (
        np.log(rates[positive]) - np.log(predictions[positive]) - 1
    )
    try:
        predicted = math.fsum(expected)
        poisson = 2 * (math.fsum(np.maximum(deviance, 0)) / total_exposure)
        mae = math.fsum(np.abs(counts - expected)) / total_exposure
    except OverflowError as exc:
        raise ValueError("Aggregate frequency metrics must be finite") from exc
    if not all(map(math.isfinite, (poisson, mae, predicted / total_exposure))):
        raise ValueError("Aggregate frequency metrics must be finite")
    # A positive rate can underflow when multiplied by a tiny exposure.
    ratio = observed / predicted if predicted > 0 else None
    return {
        "rows": len(rates),
        "exposure": total_exposure,
        "mean_poisson_deviance": poisson,
        "weighted_mae": mae,
        "observed_claims": observed,
        "observed_frequency": observed / total_exposure,
        "predicted_frequency": predicted / total_exposure,
        "predicted_claims": predicted,
        "observed_predicted_ratio": ratio if ratio is None or math.isfinite(ratio) else None,
    }


def evaluate_predictions(frame, predictions) -> dict:
    """Return exposure-weighted frequency metrics and aggregate claim totals."""
    return _metrics(*_inputs(frame, predictions))


def pure_premium(frame, loss_amounts) -> float:
    """Divide explicit per-policy monetary losses by the validated exposure total."""
    audit = validate_frame(frame)
    try:
        losses = np.asarray(loss_amounts, dtype=object)
        if (
            losses.ndim != 1
            or len(losses) != len(frame)
            or any(isinstance(loss, (bool, np.bool_)) for loss in losses)
        ):
            raise ValueError
        losses = losses.astype(float)
        if not np.all(np.isfinite(losses)) or np.any(losses < 0):
            raise ValueError
        result = math.fsum(losses) / audit["exposure"]
        if not math.isfinite(result):
            raise ValueError
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("Loss amounts must yield a finite, nonnegative loss rate") from exc
    return result


def _group_metrics(counts, exposure, predictions):
    metrics = _metrics(counts, exposure, predictions)
    reasons = []
    if metrics["rows"] < 50:
        reasons.append("rows_below_50")
    if metrics["exposure"] < 10:
        reasons.append("exposure_below_10")
    return {**metrics, "sparse": bool(reasons), "sparse_reasons": reasons}


def _positive_integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def calibration_table(frame, predictions, n_bins=10) -> list[dict]:
    """Split stable ranks into nonempty groups, retaining ties and marking sparse support."""
    _positive_integer(n_bins, "n_bins")
    counts, exposure, predictions = _inputs(frame, predictions)
    order = np.argsort(predictions, kind="stable")
    groups = np.array_split(order, min(n_bins, len(order)))
    return [
        {"bin": number, **_group_metrics(counts[index], exposure[index], predictions[index])}
        for number, index in enumerate(groups, start=1)
    ]


def segment_table(frame, predictions) -> list[dict]:
    """Describe fixed age bands and Area cells; omit empty cells."""
    counts, exposure, predictions = _inputs(frame, predictions)
    driver = frame["DrivAge"].to_numpy(dtype=float)
    vehicle = frame["VehAge"].to_numpy(dtype=float)
    segments = [
        (
            "DrivAge",
            [
                ("<25", driver < 25),
                ("25-39", (driver >= 25) & (driver < 40)),
                ("40-59", (driver >= 40) & (driver < 60)),
                ("60+", driver >= 60),
            ],
        ),
        (
            "VehAge",
            [("<5", vehicle < 5), ("5-9", (vehicle >= 5) & (vehicle < 10)), ("10+", vehicle >= 10)],
        ),
        (
            "Area",
            [
                (str(area), frame["Area"].to_numpy() == area)
                for area in sorted(frame["Area"].unique(), key=str)
            ],
        ),
    ]
    result = []
    for segment, groups in segments:
        for group, mask in groups:
            if not np.any(mask):
                continue
            result.append(
                {
                    "segment": segment,
                    "group": group,
                    **_group_metrics(counts[mask], exposure[mask], predictions[mask]),
                }
            )
    return result


def paired_bootstrap(
    frame, selected_predictions, baseline_predictions, seed=20261101, draws=200
) -> dict:
    """Pair policy indices with replacement for two frozen models on the same split.

    A single-policy draw is counted as degenerate and retained if its statistic
    is finite. A constant distribution supplies no interval evidence.
    """
    _positive_integer(draws, "draws")
    counts, exposure, selected = _inputs(frame, selected_predictions)
    _, _, baseline = _inputs(frame, baseline_predictions)
    generator = np.random.Generator(np.random.PCG64(seed))

    with np.errstate(over="ignore", invalid="ignore"):
        # The observed-rate term cancels between models before weighting.
        contributions = 2 * (
            counts * (np.log(baseline) - np.log(selected)) + exposure * (selected - baseline)
        )

    def difference(index):
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            denominator = np.sum(exposure[index])
            value = np.sum(contributions[index]) / denominator
        return float(value) if math.isfinite(denominator) and math.isfinite(value) else None

    point = difference(slice(None))
    differences = []
    degenerate = 0
    for _ in range(draws):
        index = generator.integers(0, len(frame), size=len(frame))
        value = difference(index)
        if value is not None:
            differences.append(value)
            degenerate += int(np.all(index == index[0]))

    valid = len(differences)
    invalid = draws - valid
    reason = None
    if len(frame) < BOOTSTRAP_MIN_POLICIES:
        reason = "insufficient_policies"
    elif invalid or point is None:
        reason = "invalid_draws"
    elif valid < BOOTSTRAP_MIN_VALID_DRAWS:
        reason = "insufficient_draws"
    elif min(differences) == max(differences):
        reason = "degenerate_distribution"

    lower, upper = None, None
    if reason is None:
        with np.errstate(over="ignore", invalid="ignore"):
            lower, upper = map(float, np.percentile(differences, [2.5, 97.5]))
        if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
            reason = "degenerate_distribution"
            lower = upper = None
    return {
        "selected_minus_baseline": point,
        "ci_lower": lower,
        "ci_upper": upper,
        "draws": int(draws),
        "seed": int(seed),
        "valid_draws": valid,
        "invalid_draws": int(invalid),
        "degenerate_draws": degenerate,
        "minimum_valid_draws": BOOTSTRAP_MIN_VALID_DRAWS,
        "minimum_policies": BOOTSTRAP_MIN_POLICIES,
        "confidence_level": BOOTSTRAP_CONFIDENCE_LEVEL,
        "adequate": reason is None,
        "abstention_reason": reason,
    }
