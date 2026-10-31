"""Aggregate frequency evaluation for frozen predictions on observed policies."""

import math

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance

from .data import validate_frame


def _inputs(frame, predictions):
    validate_frame(frame)
    if len(frame) == 0:
        raise ValueError("Evaluation requires at least one policy")
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
    observed = float(math.fsum(counts))
    predicted = float(np.dot(predictions, exposure))
    total_exposure = float(math.fsum(exposure))
    if not np.all(np.isfinite([observed, predicted, total_exposure])):
        raise ValueError("Aggregate counts and exposure must be finite")
    # A positive rate can underflow when multiplied by a tiny exposure.
    ratio = observed / predicted if predicted > 0 else (0.0 if observed == 0 else None)
    return {
        "rows": len(rates),
        "exposure": total_exposure,
        "mean_poisson_deviance": float(
            mean_poisson_deviance(rates, predictions, sample_weight=exposure)
        ),
        "weighted_mae": float(mean_absolute_error(rates, predictions, sample_weight=exposure)),
        "observed_claims": observed,
        "predicted_claims": predicted,
        "observed_predicted_ratio": ratio,
    }


def evaluate_predictions(frame, predictions) -> dict:
    """Return exposure-weighted frequency metrics and aggregate claim totals."""
    return _metrics(*_inputs(frame, predictions))


def _positive_integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def calibration_table(frame, predictions, n_bins=10) -> list[dict]:
    """Split stable prediction ranks into near-equal groups, retaining ties."""
    _positive_integer(n_bins, "n_bins")
    counts, exposure, predictions = _inputs(frame, predictions)
    order = np.argsort(predictions, kind="stable")
    groups = np.array_split(order, min(n_bins, len(order)))
    return [
        {"bin": number, **_metrics(counts[index], exposure[index], predictions[index])}
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
            metrics = _metrics(counts[mask], exposure[mask], predictions[mask])
            result.append(
                {
                    "segment": segment,
                    "group": group,
                    **metrics,
                    "sparse": metrics["rows"] < 50 or metrics["exposure"] < 10,
                }
            )
    return result


def paired_bootstrap(
    frame, selected_predictions, baseline_predictions, seed=20261101, draws=200
) -> dict:
    """Policy bootstrap conditional on the split and frozen fitted models.

    Each draw uses the same policy indices for both models. Negative differences
    favor the selected model. This does not describe retraining uncertainty.
    """
    _positive_integer(draws, "draws")
    counts, exposure, selected = _inputs(frame, selected_predictions)
    rates = counts / exposure
    _, _, baseline = _inputs(frame, baseline_predictions)
    generator = np.random.Generator(np.random.PCG64(seed))

    def difference(index):
        return float(
            mean_poisson_deviance(rates[index], selected[index], sample_weight=exposure[index])
            - mean_poisson_deviance(rates[index], baseline[index], sample_weight=exposure[index])
        )

    point = difference(np.arange(len(frame)))
    differences = [
        difference(generator.integers(0, len(frame), size=len(frame))) for _ in range(draws)
    ]
    lower, upper = np.percentile(differences, [2.5, 97.5])
    return {
        "selected_minus_baseline": point,
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "draws": int(draws),
        "seed": int(seed),
    }
