"""Validate the saved run and its pre-test selection without importing model code."""

import hashlib
import json
import math
import re

MODELS = ("mean", "poisson_glm", "poisson_hgb")
SELECTION_METRIC = "exposure_weighted_mean_poisson_deviance"

# Byte identities of the published benchmark, which predates the run contract.
FROZEN_RESULTS = "3585e11b57460165521a43db7b21d26dd11330c47affcec820c450c0781e1a74"
FROZEN_SELECTION = "987923727958b7d73fd8a01bb768dce566e58008a01848d2108affdedf6271e2"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _digest(value) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )


def run_identity(provenance: dict, settings: dict, splits: dict) -> dict:
    return {
        "version": 1,
        "source_sha256": provenance["source_sha256"],
        "source_md5": provenance["source_md5"],
        "code_sha256": provenance["code_sha256"],
        "config_sha256": _digest(settings),
        "split_sha256": _digest(splits),
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key in saved aggregates")
        result[key] = value
    return result


def _nonfinite(_):
    raise ValueError("Non-finite JSON number in saved aggregates")


def _float(token):
    value = float(token)
    if not math.isfinite(value):
        _nonfinite(token)
    return value


def load_saved(content: bytes) -> dict:
    value = json.loads(
        content, object_pairs_hook=_unique_object, parse_constant=_nonfinite, parse_float=_float
    )
    return _object(value, (), "aggregates")


def _require(valid, field):
    if not valid:
        raise ValueError(f"Invalid or missing saved {field}")


def _object(value, keys, field):
    _require(isinstance(value, dict) and all(key in value for key in keys), field)
    return value


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _hex(value, length):
    return isinstance(value, str) and re.fullmatch(f"[a-f0-9]{{{length}}}", value) is not None


def _support(value, count):
    _object(value, ("rows", "exposure", count), "aggregate support")
    _require(_integer(value["rows"], 1), "row count")
    _require(_number(value["exposure"]) and value["exposure"] > 0, "exposure")
    _require(_integer(value[count]), "claim count")


def _metric(value):
    _support(value, "observed_claims")
    for key in (
        "mean_poisson_deviance",
        "weighted_mae",
        "predicted_claims",
        "observed_frequency",
        "predicted_frequency",
    ):
        number = value.get(key)
        _require(_number(number) and number >= 0, key)
    for prefix in ("observed", "predicted"):
        _require(
            math.isclose(
                value[f"{prefix}_frequency"], value[f"{prefix}_claims"] / value["exposure"]
            ),
            f"{prefix} frequency",
        )
    _object(value, ("observed_predicted_ratio",), "observed/predicted ratio")
    ratio = value["observed_predicted_ratio"]
    predicted = value["predicted_claims"]
    expected = value["observed_claims"] / predicted if predicted > 0 else None
    _require(
        (_number(ratio) and math.isclose(ratio, expected)) if _number(expected) else ratio is None,
        "observed/predicted ratio",
    )


def _group_metric(value):
    _metric(value)
    reasons = []
    if value["rows"] < 50:
        reasons.append("rows_below_50")
    if value["exposure"] < 10:
        reasons.append("exposure_below_10")
    _require(
        value.get("sparse") is bool(reasons) and value.get("sparse_reasons") == reasons,
        "sparse support flags",
    )


def _reconcile(rows, parent, claims, parent_claims, field):
    _require(
        sum(row["rows"] for row in rows) == parent["rows"]
        and math.isclose(sum(row["exposure"] for row in rows), parent["exposure"])
        and sum(row[claims] for row in rows) == parent[parent_claims],
        field,
    )


def _bootstrap(value, settings, test_rows, selected_deviance, mean_deviance):
    keys = (
        "selected_minus_baseline",
        "ci_lower",
        "ci_upper",
        "draws",
        "seed",
        "adequate",
        "valid_draws",
        "invalid_draws",
        "degenerate_draws",
        "minimum_valid_draws",
        "minimum_policies",
        "confidence_level",
        "abstention_reason",
    )
    _object(value, keys, "bootstrap")
    draws, valid, invalid, degenerate, minimum = (
        value[key]
        for key in (
            "draws",
            "valid_draws",
            "invalid_draws",
            "degenerate_draws",
            "minimum_valid_draws",
        )
    )
    _require(
        value["confidence_level"] == 0.95 and value["minimum_policies"] == 2,
        "bootstrap confidence or minimum policies",
    )
    _require(
        all(_integer(number) for number in (draws, valid, invalid, degenerate, minimum))
        and draws == settings["bootstrap_draws"]
        and valid + invalid == draws
        and degenerate <= valid
        and minimum == 40
        and _integer(value["seed"])
        and value["seed"] == settings["seed"],
        "bootstrap draw counts or settings",
    )
    point, lower, upper = (
        value[key] for key in ("selected_minus_baseline", "ci_lower", "ci_upper")
    )
    _require(point is None or _number(point), "bootstrap point estimate")
    if point is not None:
        _require(
            math.isclose(
                point,
                selected_deviance - mean_deviance,
                abs_tol=1e-12 * max(1, selected_deviance, mean_deviance),
            ),
            "bootstrap point estimate from test scores",
        )
    adequate, reason = value["adequate"], value["abstention_reason"]
    _require(type(adequate) is bool, "bootstrap adequacy")
    if adequate:
        _require(
            reason is None
            and test_rows >= value["minimum_policies"]
            and valid >= minimum
            and invalid == 0
            and _number(point)
            and _number(lower)
            and _number(upper)
            and lower < upper,
            "bootstrap interval",
        )
    else:
        _require(
            lower is None
            and upper is None
            and reason
            in (
                "insufficient_policies",
                "invalid_draws",
                "insufficient_draws",
                "degenerate_distribution",
            ),
            "bootstrap abstention",
        )


def validate_run(results: dict, selection: dict) -> dict:
    _object(
        results,
        (
            "run_identity",
            "selected_model",
            "study",
            "provenance",
            "audit",
            "splits",
            "metrics",
            "calibration",
            "segments",
            "eda",
            "bootstrap",
            "limitations",
        ),
        "results domain fields or run identity",
    )
    study = _object(
        results["study"],
        ("name", "seed", "sampled", "rows", "data_kind", "settings", "selection_split"),
        "study",
    )
    _require(
        study["name"] == "MotorClaimLab"
        and type(study["sampled"]) is bool
        and study["data_kind"] in ("openml_pinned", "local_unverified")
        and study["selection_split"] == "validation"
        and _integer(study["seed"]),
        "study or selection split",
    )
    settings = _object(
        study["settings"],
        (
            "seed",
            "max_rows",
            "max_iter",
            "bootstrap_draws",
            "thread_limit",
            "split_method",
            "test_used_for_selection",
            "glm",
            "hgb",
        ),
        "settings",
    )
    _require(
        _integer(settings["seed"])
        and settings["seed"] == study["seed"]
        and all(
            _integer(settings[key], 1) for key in ("max_iter", "bootstrap_draws", "thread_limit")
        )
        and (settings["max_rows"] is None or _integer(settings["max_rows"], 1))
        and settings["split_method"] == "sha256-policy-id-60-20-20"
        and settings["test_used_for_selection"] is False,
        "settings",
    )
    _object(settings["glm"], ("alpha", "max_iter", "tol"), "GLM settings")
    _object(
        settings["hgb"],
        (
            "max_iter",
            "max_leaf_nodes",
            "min_samples_leaf",
            "learning_rate",
            "early_stopping",
            "loss",
        ),
        "HGB settings",
    )
    provenance = _object(
        results["provenance"],
        ("source_sha256", "source_md5", "code_sha256", "source_matches_pinned", "source_capture"),
        "provenance",
    )
    _require(
        all(_hex(provenance[key], 64) for key in ("source_sha256", "code_sha256"))
        and _hex(provenance["source_md5"], 32)
        and provenance["source_capture"] == "bounded_snapshot"
        and provenance["source_matches_pinned"] is (study["data_kind"] == "openml_pinned"),
        "input or code fingerprint",
    )
    _support(results["audit"], "claims")
    splits = _object(results["splits"], ("train", "validation", "test"), "splits")
    _require(set(splits) == {"train", "validation", "test"}, "splits")
    for split in splits.values():
        _support(split, "claims")
        _require(_hex(split.get("membership_sha256"), 64), "split fingerprint")
    _require(
        _integer(study["rows"], 1)
        and study["rows"] == sum(split["rows"] for split in splits.values())
        and study["rows"] <= results["audit"]["rows"]
        and study["sampled"] == (study["rows"] < results["audit"]["rows"]),
        "study and split row counts",
    )
    if study["sampled"]:
        exposure = sum(split["exposure"] for split in splits.values())
        audited = results["audit"]
        _require(
            (exposure <= audited["exposure"] or math.isclose(exposure, audited["exposure"]))
            and sum(split["claims"] for split in splits.values()) <= audited["claims"],
            "sampled support within audit",
        )
    else:
        _reconcile(list(splits.values()), results["audit"], "claims", "claims", "full input audit")
    expected = run_identity(provenance, settings, splits)
    _require(_digest(results["run_identity"]) == _digest(expected), "run identity fingerprints")
    metrics = _object(results["metrics"], ("validation", "test"), "metrics")
    for name in ("validation", "test"):
        models = _object(metrics[name], MODELS, "model metrics")
        _require(set(models) == set(MODELS), "model metrics")
        for value in models.values():
            _metric(value)
            _require(
                value["rows"] == splits[name]["rows"]
                and math.isclose(value["exposure"], splits[name]["exposure"], rel_tol=1e-9)
                and value["observed_claims"] == splits[name]["claims"],
                "metric support for its split",
            )
    selected = min(MODELS, key=lambda model: metrics["validation"][model]["mean_poisson_deviance"])
    _require(results["selected_model"] == selected, "selected model for validation")
    _object(
        selection,
        ("run_identity", "selected_model", "selection_split", "metric", "settings", "validation"),
        "selection domain fields or run identity",
    )
    _require(
        selection["selected_model"] == selected
        and selection["selection_split"] == "validation"
        and selection["metric"] == SELECTION_METRIC
        and _digest(selection["run_identity"]) == _digest(expected)
        and _digest(selection["settings"]) == expected["config_sha256"]
        and _digest(selection["validation"]) == _digest(metrics["validation"]),
        "selection matching the results model, split, metric, validation or fingerprints",
    )
    calibration = _object(results["calibration"], MODELS, "calibration")
    _require(set(calibration) == set(MODELS), "calibration models")
    for model, bins in calibration.items():
        _require(isinstance(bins, list) and bool(bins), "calibration bins")
        for index, bin_ in enumerate(bins, start=1):
            _group_metric(bin_)
            _require(_integer(bin_.get("bin"), 1) and bin_["bin"] == index, "calibration bin rank")
        _reconcile(
            bins, splits["test"], "observed_claims", "claims", "calibration support for test split"
        )
        _require(
            math.isclose(
                sum(row["predicted_claims"] for row in bins),
                metrics["test"][model]["predicted_claims"],
            ),
            "calibration predicted claims for test split",
        )
    segments = results["segments"]
    _require(isinstance(segments, list) and bool(segments), "segments")
    for segment in segments:
        _group_metric(segment)
        _require(
            segment.get("segment") in ("Area", "DrivAge", "VehAge")
            and isinstance(segment.get("group"), str)
            and bool(segment["group"]),
            "segment labels and support",
        )
    for dimension in ("Area", "DrivAge", "VehAge"):
        rows = [segment for segment in segments if segment["segment"] == dimension]
        _reconcile(
            rows, splits["test"], "observed_claims", "claims", "segment support for test split"
        )
        _require(
            math.isclose(
                sum(row["predicted_claims"] for row in rows),
                metrics["test"][selected]["predicted_claims"],
            ),
            "segment predicted claims for selected model test split",
        )
        _require(len({row["group"] for row in rows}) == len(rows), "distinct segment groups")
    eda = _object(results["eda"], ("overall", "by_area"), "EDA")
    _support(eda["overall"], "claims")
    _require(isinstance(eda["by_area"], list) and bool(eda["by_area"]), "EDA area aggregates")
    for area in eda["by_area"]:
        _support(area, "claims")
        _require(isinstance(area.get("area"), str) and bool(area["area"]), "EDA area label")
    _require(
        len({area["area"] for area in eda["by_area"]}) == len(eda["by_area"]), "distinct EDA areas"
    )
    for row in (eda["overall"], *eda["by_area"]):
        rate = row.get("frequency")
        _require(
            _number(rate) and math.isclose(rate, row["claims"] / row["exposure"]), "EDA frequency"
        )
    _reconcile(list(splits.values()), eda["overall"], "claims", "claims", "EDA support for study")
    _reconcile(eda["by_area"], eda["overall"], "claims", "claims", "EDA area support for study")
    _bootstrap(
        results["bootstrap"],
        settings,
        splits["test"]["rows"],
        metrics["test"][selected]["mean_poisson_deviance"],
        metrics["test"]["mean"]["mean_poisson_deviance"],
    )
    _require(
        isinstance(results["limitations"], list)
        and all(isinstance(note, str) for note in results["limitations"]),
        "limitations",
    )
    return expected
