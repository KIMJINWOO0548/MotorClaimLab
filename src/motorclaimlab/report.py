"""Offline aggregate HTML, Markdown, and SVG reporting."""

# Long HTML template lines are kept intact so the markup remains easy to scan.
# ruff: noqa: E501

from __future__ import annotations

import html
import json
import math
import re
from io import StringIO
from numbers import Real
from pathlib import Path
from typing import Any

from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure

_MODELS = ("mean", "poisson_glm", "poisson_hgb")
RENDERER_VERSION = "3.4"
_MODEL_LABELS = {
    "mean": "Training mean",
    "poisson_glm": "Poisson GLM",
    "poisson_hgb": "Poisson HGB",
}
_SEGMENT_LABELS = {"DrivAge": "운전자 연령", "VehAge": "차량 연령", "Area": "지역"}


def write_uncertainty(results: dict, directory: Path) -> Path:
    """Export only the stored paired difference, never per-model error bars."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    svg = _uncertainty_svg(results, directory)
    path = directory / "paired-difference.svg"
    path.write_bytes(('<?xml version="1.0" encoding="utf-8"?>\n' + svg).encode("utf-8"))
    return path


def _number(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{number:,.{digits}f}" if math.isfinite(number) else "N/A"


def _integer(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError, OverflowError):
        return "N/A"


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _study_exposure(results: dict) -> float | None:
    """Pair study rows only with complete, valid saved split-population totals."""
    study, splits = results.get("study"), results.get("splits")
    if not isinstance(study, dict) or not isinstance(splits, dict):
        return None
    if set(splits) != {"train", "validation", "test"}:
        return None

    def positive(value):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Expected a numeric aggregate")
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError("Expected a positive finite aggregate")
        return number

    def row_count(value):
        number = positive(value)
        if not number.is_integer() or int(number) != value:
            raise ValueError("Expected an exact integer row count")
        return int(number)

    try:
        study_rows = row_count(study.get("rows"))
        rows, exposures = [], []
        for name in ("train", "validation", "test"):
            split = splits[name]
            if not isinstance(split, dict):
                return None
            rows.append(row_count(split.get("rows")))
            exposures.append(positive(split.get("exposure")))
        if sum(rows) != study_rows:
            return None
        exposure = math.fsum(exposures)
        return exposure if math.isfinite(exposure) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _source_description(results: dict) -> str:
    pinned = (
        results.get("study", {}).get("data_kind") == "openml_pinned"
        and results.get("provenance", {}).get("source_matches_pinned") is True
    )
    if pinned:
        return "과거 프랑스 자료에 대한 공개 데이터 실험입니다."
    return "로컬 입력 자료에 대한 실험입니다. 자료의 출처와 실제·합성 여부는 확인하지 않았습니다."


def _prediction_direction(metric: dict) -> str:
    """Describe saved aggregate count differences without imposing a decision threshold."""
    counts = [metric.get("observed_claims"), metric.get("predicted_claims")]
    if any(
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
        or value < 0
        for value in counts
    ):
        return "판정 불가 · N/A"
    difference = counts[0] - counts[1]
    if not math.isfinite(difference):
        return "판정 불가 · N/A"
    if difference > 0:
        return f"과소예측 · +{_number(difference, 2)}"
    if difference < 0:
        return f"과대예측 · {_number(difference, 2)}"
    return "일치 · 0.00"


def segment_review(results: dict) -> list[dict]:
    """Review each saved partition independently; totals do not prove membership.

    Fail closed for incomplete/invalid support, duplicate group names or totals
    inconsistent with the selected model's saved test metrics. No thresholds,
    selection changes, causal interpretation or cross-dimension summation.
    """
    dimensions: dict[str, list[dict]] = {}
    for row in results.get("segments", []):
        dimensions.setdefault(str(row.get("segment", "기록 없음")), []).append(row)
    target = results.get("metrics", {}).get("test", {}).get(results.get("selected_model"), {})
    fields = ("rows", "exposure", "observed_claims", "predicted_claims")

    def valid(metric: dict) -> bool:
        for key in fields:
            value = metric.get(key)
            if isinstance(value, bool) or not isinstance(value, Real):
                return False
            try:
                if not math.isfinite(value):
                    return False
            except OverflowError:
                return False
            if value < 0 or (key in ("rows", "exposure") and value <= 0):
                return False
            if key == "rows" and int(value) != value:
                return False
        return True

    reviews = []
    for name, rows in dimensions.items():
        review = {
            "dimension": name,
            "groups": len(rows),
            "reconciled": False,
            "rows": None,
            "exposure": None,
            "net_gap": None,
            "absolute_gap": None,
            "under": None,
            "over": None,
        }
        labels = [row.get("group") for row in rows]
        if (
            not valid(target)
            or not all(valid(row) for row in rows)
            or not all(isinstance(label, str) and label for label in labels)
            or len(set(labels)) != len(labels)
        ):
            reviews.append(review)
            continue
        try:
            totals = {key: math.fsum(row[key] for row in rows) for key in fields[1:]}
            totals["rows"] = sum(int(row["rows"]) for row in rows)
            reconciled = totals["rows"] == target["rows"] and all(
                math.isclose(totals[key], target[key], rel_tol=1e-9, abs_tol=1e-9)
                for key in fields[1:]
            )
            gaps = [row["observed_claims"] - row["predicted_claims"] for row in rows]
            absolute = math.fsum(abs(gap) for gap in gaps)
            net = math.fsum(gaps)
            if not reconciled or not all(
                math.isfinite(value) for value in (*totals.values(), absolute, net)
            ):
                reviews.append(review)
                continue
        except (OverflowError, ValueError):
            reviews.append(review)
            continue

        def finding(row: dict, gap: float) -> dict:
            return {
                "group": row["group"],
                "gap": gap,
                "rows": row["rows"],
                "exposure": row["exposure"],
                "exposure_share": row["exposure"] / target["exposure"],
                "sparse": row.get("sparse") is True,
            }

        # max/min retain saved order for exact ties; there is no inferred significance.
        under = max(range(len(rows)), key=lambda index: gaps[index])
        over = min(range(len(rows)), key=lambda index: gaps[index])
        review.update(
            reconciled=True,
            rows=target["rows"],
            exposure=target["exposure"],
            net_gap=net,
            absolute_gap=absolute,
            under=finding(rows[under], gaps[under]) if gaps[under] > 0 else None,
            over=finding(rows[over], gaps[over]) if gaps[over] < 0 else None,
        )
        reviews.append(review)
    return reviews


def _finding_text(finding: dict | None) -> str:
    if finding is None:
        return "해당 방향 차이 없음"
    return (
        f"{finding['group']} · {finding['gap']:+,.2f}건 · {_integer(finding['rows'])} rows · "
        f"{_number(finding['exposure'], 2)} exposure-years ({finding['exposure_share']:.1%})"
        + (" · Sparse" if finding["sparse"] else "")
    )


def _segment_review_html(results: dict) -> str:
    rows = []
    for index, review in enumerate(segment_review(results)):
        label = _SEGMENT_LABELS.get(review["dimension"], review["dimension"])
        heading = (
            f'<h4><a href="#segment-dimension-{index}">{_e(label)} · '
            f"{review['groups']}개 집단 상세 표로 이동</a></h4>"
        )
        if not review["reconciled"]:
            body = '<p class="review-unavailable">저장 합계 확인 불가 · N/A. 행·노출·관측/예측 합계 또는 집단 이름을 확인하세요. 합산 차이·노출 비중·최대 차이는 계산하지 않습니다.</p>'
        else:
            body = (
                f'<p class="review-support">저장 합계 일치 · {_integer(review["rows"])} test rows · '
                f"{_number(review['exposure'], 2)} exposure-years</p>"
                '<dl class="review-gap"><div><dt>순 차이 · Net group gap</dt>'
                f"<dd>{review['net_gap']:+,.2f}건</dd></div><div><dt>집단별 절대 차이 합 · Absolute group gap</dt>"
                f"<dd>{review['absolute_gap']:,.2f}건</dd></div></dl>"
                f"<p><strong>가장 큰 과소예측</strong> {_e(_finding_text(review['under']))}</p>"
                f"<p><strong>가장 큰 과대예측</strong> {_e(_finding_text(review['over']))}</p>"
            )
        rows.append(f'<article class="segment-review-row">{heading}{body}</article>')
    return (
        '<div id="segment-review" class="segment-review"><h3>합계에 가려진 집단 차이 조사</h3>'
        "<p>각 차원 안에서 관측 − 예측의 순 차이와 절대 차이 합을 함께 보세요. 순 차이가 작아도 반대 방향 차이가 상쇄될 수 있습니다. "
        "최대 차이는 건수 기준의 탐색 순서이며 위험·공정성·유의성 순위가 아닙니다. 동률은 저장 순서를 따릅니다.</p>"
        '<p class="muted">노출 비중의 분모는 선택 모델의 저장된 test 노출 합계입니다. 행·노출·관측/예측 건수를 각각 대조합니다. '
        "합계 일치는 원자료의 중복·누락 검증이 아닙니다. 차원 간 집단은 겹치므로 합산하지 마세요. Sparse는 기존 저장 표시를 유지합니다.</p>"
        + ("".join(rows) if rows else '<p class="review-unavailable">저장된 집단 없음 · N/A</p>')
        + "</div>"
    )


def _metric_table(rows: list[tuple[str, dict]], caption: str, *, direction: bool = False) -> str:
    body = "".join(
        "<tr>"
        + f"<th scope='row'>{_e(label + (' · Sparse' if metric.get('sparse') else ''))}</th>"
        + f"<td>{_integer(metric.get('rows'))}</td>"
        + f"<td>{_number(metric.get('exposure'), 2)}</td>"
        + f"<td>{_number(metric.get('mean_poisson_deviance'))}</td>"
        + f"<td>{_number(metric.get('weighted_mae'))}</td>"
        + f"<td>{_number(metric.get('observed_claims'), 2)}</td>"
        + f"<td>{_number(metric.get('predicted_claims'), 2)}</td>"
        + f"<td>{_number(metric.get('observed_predicted_ratio'))}</td>"
        + (f"<td>{_prediction_direction(metric)}</td>" if direction else "")
        + "</tr>"
        for label, metric in rows
    )
    return (
        f"<div class='table-wrap' tabindex='0' role='region' aria-label='{_e(caption)}'><table><caption>{_e(caption)}</caption>"
        "<thead><tr><th scope='col'>Model / group</th><th scope='col'>Rows</th>"
        "<th scope='col'>Exposure (years)</th><th scope='col'>Poisson deviance</th>"
        "<th scope='col'>Weighted MAE</th><th scope='col'>Observed claims</th>"
        "<th scope='col'>Predicted claims</th><th scope='col'>Observed / predicted</th>"
        + ("<th scope='col'>Observed − predicted (claims)</th>" if direction else "")
        + f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _figure_svg(figure: Figure, key: str) -> str:
    import matplotlib

    output = StringIO()
    with matplotlib.rc_context(
        {
            "svg.hashsalt": f"MotorClaimLab-{RENDERER_VERSION}-{key}",
            "svg.fonttype": "none",
            "font.family": "DejaVu Sans",
        }
    ):
        FigureCanvasSVG(figure).print_svg(output, metadata={"Date": None})
    value = output.getvalue()
    return "\n".join(line.rstrip() for line in value[value.find("<svg") :].splitlines()) + "\n"


def _inline_svg(svg: str, key: str, title: str) -> str:
    """Namespace document IDs when multiple standalone SVGs share one HTML page."""
    for identifier in re.findall(r'\bid="([^"]+)"', svg):
        replacement = f"{key}-{identifier}"
        svg = svg.replace(f'id="{identifier}"', f'id="{replacement}"')
        svg = svg.replace(f'#{identifier}"', f'#{replacement}"')
        svg = svg.replace(f"#{identifier})", f"#{replacement})")
    return re.sub(
        r"(<svg\b[^>]*)(>)",
        lambda match: (
            match[1]
            + f' role="img" aria-labelledby="{key}-title"'
            + match[2]
            + f'<title id="{key}-title">{_e(title)}</title>'
        ),
        svg,
        count=1,
    )


def _interval_values(results: dict):
    boot = results.get("bootstrap", {})
    try:
        raw = [boot[name] for name in ("selected_minus_baseline", "ci_lower", "ci_upper")]
        if any(isinstance(value, bool) for value in raw):
            return None
        point, lower, upper = map(float, raw)
        if not all(math.isfinite(value) for value in (point, lower, upper)) or lower > upper:
            return None
        if results.get("selected_model") == "mean" and any(
            value != 0 for value in (point, lower, upper)
        ):
            return None
        return point, lower, upper
    except (KeyError, TypeError, ValueError):
        return None


def _uncertainty_svg(results: dict, directory: Path | None = None) -> str:
    figure = Figure(figsize=(8.2, 2.9), layout="constrained")
    axis = figure.subplots()
    values = _interval_values(results)
    if values is None:
        axis.text(0.5, 0.5, "Interval unavailable (not computed)", ha="center", va="center")
        axis.set_axis_off()
    else:
        point, lower, upper = values
        zero = axis.axvline(0, color="#596574", linewidth=1.2, linestyle="--")
        zero.set_gid("zero-reference")
        interval = axis.hlines(0.5, lower, upper, colors="#315bdf", linewidth=5)
        interval.set_gid("paired-ci")
        axis.vlines([lower, upper], 0.44, 0.56, colors="#315bdf", linewidth=1.4)
        (marker,) = axis.plot(point, 0.5, marker="D", color="#102c3b", markersize=8)
        marker.set_gid("paired-point")
        axis.annotate(
            f"{lower:.5f}",
            (lower, 0.5),
            xytext=(-4, 16),
            textcoords="offset points",
            ha="right",
            fontsize=9,
        )
        axis.annotate(
            f"{upper:.5f}",
            (upper, 0.5),
            xytext=(4, 16),
            textcoords="offset points",
            ha="left",
            fontsize=9,
        )
        axis.annotate(
            f"difference {point:.5f}",
            (point, 0.5),
            xytext=(0, -23),
            textcoords="offset points",
            ha="center",
            fontsize=9,
        )
        lo, hi = min(0, lower, point), max(0, upper, point)
        padding = max(hi - lo, 0.01) * 0.28
        axis.set_xlim(lo - padding, hi + padding)
        axis.set_ylim(0, 1)
        axis.set_yticks([])
        axis.text(0, 0.92, "0 = no difference", ha="center", fontsize=8)
        axis.set_xlabel("Selected - baseline deviance (negative favors selected)")
        axis.set_title(
            f"{_MODEL_LABELS.get(results.get('selected_model'), results.get('selected_model', 'N/A'))} - Training mean\n95% paired interval (bootstrap) · Frozen fits and split",
            loc="left",
            fontsize=11,
        )
        axis.grid(axis="x", alpha=0.18)
        for name in ("top", "right", "left"):
            axis.spines[name].set_visible(False)
    svg = _figure_svg(figure, "paired-difference")
    if directory is not None:
        figure.savefig(directory / "paired-difference.png", dpi=160)
    figure.clear()
    return svg


def _calibration_support(results: dict) -> str:
    """Describe the highest saved rank with the same repeated-bin totals as the plot."""
    rows = results.get("calibration", {}).get(results.get("selected_model"), [])
    unavailable = "Support unavailable (N/A)"
    try:
        ranks = [float(row["bin"]) for row in rows]
        if (
            not ranks
            or any(isinstance(row["bin"], bool) for row in rows)
            or not all(map(math.isfinite, ranks))
        ):
            return unavailable
        rank = max(ranks)
        group = [row for row, value in zip(rows, ranks, strict=True) if value == rank]
        columns = ("rows", "exposure", "observed_claims", "predicted_claims")
        values = []
        for row in group:
            if any(isinstance(row[name], bool) for name in columns):
                return unavailable
            count, exposure, observed, predicted = [float(row[name]) for name in columns]
            if (
                not all(map(math.isfinite, (count, exposure, observed, predicted)))
                or count < 0
                or not count.is_integer()
                or exposure <= 0
                or observed < 0
                or predicted < 0
            ):
                return unavailable
            values.append((count, exposure, observed, predicted))
        count, exposure, observed, predicted = [
            math.fsum(column) for column in zip(*values, strict=True)
        ]
        return (
            f"Bin {rank:g} · {_integer(count)} rows · {_number(exposure, 2)} exposure-years\n"
            f"Observed {_number(observed, 2)} claims / Predicted {_number(predicted, 2)} claims"
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return unavailable


def _figures(results: dict, directory: Path | None = None) -> tuple[str, str]:
    import matplotlib

    matplotlib.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    comparison = Figure(figsize=(8.2, 4.2), layout="constrained")
    axis = comparison.subplots()
    metrics = results.get("metrics", {}).get("test", {})
    vals = [metrics.get(name, {}).get("mean_poisson_deviance") for name in _MODELS]
    plot_vals = [
        float(v) if v is not None and math.isfinite(float(v)) else float("nan") for v in vals
    ]
    bars = axis.barh(
        [_MODEL_LABELS[name] for name in _MODELS],
        plot_vals,
        color=[
            "#315bdf" if name == results.get("selected_model") else "#b9c7d3" for name in _MODELS
        ],
        height=0.48,
    )
    axis.set_title(
        "Test-set Poisson deviance", loc="left", pad=18, color="#102c3b", fontweight="bold"
    )
    axis.set_xlabel("Exposure-weighted deviance · lower is better")
    axis.invert_yaxis()
    axis.margins(x=0.22, y=0.25)
    axis.grid(axis="x", alpha=0.16)
    axis.tick_params(axis="y", length=0, pad=10, colors="#102c3b")
    for name in ("top", "right", "left"):
        axis.spines[name].set_visible(False)
    axis.set_axisbelow(True)
    comparison.supxlabel(
        f"Selected on validation: {_MODEL_LABELS.get(results.get('selected_model'), results.get('selected_model', 'N/A'))}; test shown after selection.",
        fontsize=8,
        color="#526574",
    )
    for bar, value in zip(bars, vals, strict=True):
        axis.annotate(
            _number(value, 6),
            (bar.get_width(), bar.get_y() + bar.get_height() / 2),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=10,
            color="#102c3b",
        )
    comparison_svg = _figure_svg(comparison, "model-comparison")
    if directory is not None:
        comparison.savefig(directory / "model-comparison.png", dpi=160)
    comparison.clear()

    selected = str(results.get("selected_model", ""))
    calibration_rows = results.get("calibration", {}).get(selected, [])
    by_bin: dict[Any, list[dict]] = {}
    for row in calibration_rows:
        by_bin.setdefault(row.get("bin"), []).append(row)
    bins = sorted(
        by_bin, key=lambda value: (value is None, float(value) if value is not None else 0)
    )
    labels = []
    observed_rates = []
    predicted_rates = []
    incomplete_bins = []
    for bin_number in bins:
        group = by_bin[bin_number]
        labels.append(str(bin_number))
        try:
            values = [
                [float(row[name]) for name in ("exposure", "observed_claims", "predicted_claims")]
                for row in group
            ]
            if any(
                not all(math.isfinite(value) for value in row)
                or row[0] <= 0
                or row[1] < 0
                or row[2] < 0
                for row in values
            ):
                raise ValueError("Incomplete calibration totals")
            exposure, observed, predicted = [
                math.fsum(column) for column in zip(*values, strict=True)
            ]
            observed_rates.append(observed / exposure)
            predicted_rates.append(predicted / exposure)
        except (KeyError, TypeError, ValueError, OverflowError):
            observed_rates.append(float("nan"))
            predicted_rates.append(float("nan"))
            incomplete_bins.append(str(bin_number))
    calibration = Figure(figsize=(8.2, 4.9), layout="constrained", facecolor="#102c3b")
    axis = calibration.subplots()
    axis.set_facecolor("#102c3b")
    positions = list(range(len(labels)))
    axis.plot(
        positions,
        observed_rates,
        marker="o",
        color="#8ec7ef",
        label="Observed rate",
        linewidth=2.8,
        markersize=6,
    )
    axis.plot(
        positions,
        predicted_rates,
        marker="s",
        linestyle="--",
        color="#ff956d",
        label="Predicted rate",
        linewidth=2.3,
        markersize=5,
    )
    for x, value in zip(positions, observed_rates, strict=True):
        if not math.isfinite(value) or x not in (0, len(labels) - 1):
            continue
        axis.annotate(
            f"Observed {_number(value, 3)}" if x == len(labels) - 1 else _number(value, 3),
            (x, value),
            xytext=(8, 8) if x == len(labels) - 1 else (0, 8),
            textcoords="offset points",
            ha="left" if x == len(labels) - 1 else "center",
            fontsize=8,
            color="#8ec7ef",
        )
    for x, value in zip(positions, predicted_rates, strict=True):
        if not math.isfinite(value) or x not in (0, len(labels) - 1):
            continue
        axis.annotate(
            f"Predicted {_number(value, 3)}" if x == len(labels) - 1 else _number(value, 3),
            (x, value),
            xytext=(8, -14) if x == len(labels) - 1 else (0, -14),
            textcoords="offset points",
            ha="left" if x == len(labels) - 1 else "center",
            fontsize=8,
            color="#ff956d",
        )
    axis.set_xticks(positions, labels)
    axis.set_title(
        f"Calibration by prediction bin — {_MODEL_LABELS.get(selected, selected)}",
        loc="left",
        color="white",
        fontsize=11,
        pad=18,
    )
    axis.set_xlabel("Prediction bin (rank, not time)", color="#c4d4dd", labelpad=10)
    axis.set_ylabel("Claim frequency (claims / exposure year)", color="#c4d4dd", labelpad=10)
    axis.tick_params(colors="#c4d4dd", length=0, pad=8)
    axis.margins(x=0.1, y=0.18)
    if labels:
        axis.set_xlim(-0.6, max(len(labels) - 1, 1) + 2)
    axis.set_axisbelow(True)
    axis.grid(axis="y", color="#c4d4dd", alpha=0.14)
    axis.legend(frameon=False, labelcolor="#ffffff", loc="upper left")
    for name, spine in axis.spines.items():
        spine.set_visible(name == "bottom")
        spine.set_color("#547383")
    if incomplete_bins:
        calibration.suptitle(
            "Incomplete calibration bins: " + ", ".join(incomplete_bins),
            x=0.02,
            ha="left",
            fontsize=10,
            color="#ff956d",
        )
    calibration.supxlabel(
        _calibration_support(results), fontsize=9, color="#c4d4dd", ha="left", x=0.025
    )
    calibration_svg = _figure_svg(calibration, "calibration")
    if directory is not None:
        calibration.savefig(directory / "calibration.png", dpi=160)
    calibration.clear()
    return comparison_svg, calibration_svg


def write_figures(results: dict, directory: Path) -> list[Path]:
    """Write the report's original standalone SVG charts and return their paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    comparison, calibration = _figures(results, directory)
    paths = [directory / "model-comparison.svg", directory / "calibration.svg"]
    for path, contents in zip(paths, (comparison, calibration), strict=True):
        path.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + contents, encoding="utf-8")
    return paths


def render_markdown(results: dict) -> str:
    """Portable aggregate comparison with the same saved context as the HTML view."""
    study = results.get("study", {})
    lines = [
        "# MotorClaimLab · frozen-result comparison",
        "",
        _source_description(results),
        "",
        f"- Selected model: {_e(results.get('selected_model', 'N/A'))} (selected on {_e(study.get('selection_split', 'N/A'))})",
        f"- Rows: {_integer(study.get('rows'))}; data kind: {_e(study.get('data_kind', 'N/A'))}; seed: {_e(study.get('seed', 'N/A'))}",
        f"- Study exposure: {_number(_study_exposure(results), 2)} years (saved train/validation/test population).",
        f"- Full-input audit: {_integer(results.get('audit', {}).get('rows'))} rows; exposure {_number(results.get('audit', {}).get('exposure'), 2)} years.",
        f"- Renderer {RENDERER_VERSION}; source values are saved aggregates; no model execution.",
        "",
        "## Validation and test comparison",
        "",
        "| Model | Validation deviance | Test deviance | Test weighted MAE | Observed claims | Predicted claims | Ratio |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in _MODELS:
        validation = results.get("metrics", {}).get("validation", {}).get(name, {})
        test = results.get("metrics", {}).get("test", {}).get(name, {})
        note = " · 검증 분할에서 선택" if name == results.get("selected_model") else ""
        lines.append(
            f"| {_MODEL_LABELS[name]}{note} | {_number(validation.get('mean_poisson_deviance'), 6)} | "
            f"{_number(test.get('mean_poisson_deviance'), 6)} | {_number(test.get('weighted_mae'), 6)} | "
            f"{_number(test.get('observed_claims'), 2)} | {_number(test.get('predicted_claims'), 2)} | "
            f"{_number(test.get('observed_predicted_ratio'))} |"
        )
    lines.extend(["", "## Paired uncertainty", ""])
    values = _interval_values(results)
    if values is None:
        lines.append(
            "계산되지 않음: 저장 구간이 없거나 유효하지 않습니다. 0 또는 통과 상태로 대체하지 않습니다."
        )
    else:
        point, lower, upper = values
        lines.append(
            f"{_e(_MODEL_LABELS.get(results.get('selected_model'), results.get('selected_model', 'N/A')))} − Training mean: **{point:.5f}**; 95% paired interval **[{lower:.5f}, {upper:.5f}]**."
        )
        lines.append(
            f"반복 {_integer(results.get('bootstrap', {}).get('draws'))}; seed {_e(results.get('bootstrap', {}).get('seed', 'N/A'))}."
        )
        if results.get("selected_model") == "mean":
            lines.append("기준 모델과 동일한 비교입니다. 개선 효과를 주장하지 않습니다.")
    lines.extend(
        [
            "0은 차이 없음이며 음수는 선택 모델에 유리합니다. 구간은 고정 분할과 frozen fits에 조건부이며 재학습·미래 시점 불확실성을 포함하지 않습니다.",
            "",
            _provenance(results),
            "",
            "## Selected-model segments",
            "",
            "청구 건수의 기술적 차이: 관측 − 예측이 양수면 과소예측, 음수면 과대예측입니다. 인과 설명·보험금 판단·유의성 판정이 아닙니다.",
            "",
            "| Segment / group | Rows | Exposure | Poisson deviance | Observed / predicted | Observed − predicted (claims) |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    review_lines = [
        "### Segment review — saved test aggregates",
        "",
        "Net group gap sums observed minus predicted within one dimension; Absolute group gap sums absolute differences. Opposing errors can cancel.",
        "Exposure shares use the selected model's saved test exposure. Rows, exposure and observed/predicted totals are checked separately. Matching totals do not prove disjoint/full row membership. Do not add overlapping dimensions. Largest differences are descriptive counts, not risk, significance or fairness ranks; exact ties retain saved order.",
        "",
    ]
    for review in segment_review(results):
        dimension = _e(review["dimension"]).replace("|", "&#124;").replace("\n", " ")
        review_lines.append(f"- **{dimension}** ({review['groups']} groups)")
        if not review["reconciled"]:
            review_lines.append(
                "  Saved totals unavailable/inconsistent — N/A; combined gaps, shares and largest differences suppressed."
            )
            continue
        review_lines.extend(
            [
                f"  Saved totals consistent: {_integer(review['rows'])} test rows; {_number(review['exposure'], 2)} exposure-years.",
                f"  Net group gap: {review['net_gap']:+,.2f}; Absolute group gap: {review['absolute_gap']:,.2f} claims.",
                "  Largest underprediction: "
                + _e(_finding_text(review["under"])).replace("|", "&#124;").replace("\n", " "),
                "  Largest overprediction: "
                + _e(_finding_text(review["over"])).replace("|", "&#124;").replace("\n", " "),
            ]
        )
    # Insert the investigation before, rather than inside, the original Markdown table.
    lines[-2:-2] = review_lines + [""]
    for row in results.get("segments", []):
        label = f"{row.get('segment', '')}: {row.get('group', '')}"
        if row.get("sparse"):
            label += " · Sparse"
        label = _e(label).replace("|", "&#124;").replace("\n", " ")
        lines.append(
            f"| {label} | {_integer(row.get('rows'))} | {_number(row.get('exposure'), 2)} | "
            f"{_number(row.get('mean_poisson_deviance'))} | {_number(row.get('observed_predicted_ratio'))} | {_prediction_direction(row)} |"
        )
    lines.extend(
        [
            "",
            "Sparse: rows < 50 or exposure < 10 years. Metrics are observations, not an approval/compliance status.",
            "",
            "## Limitations",
            "",
            "- 빈도는 청구 건수 / 관측 노출 연수이며 적합·평가에 노출 가중치를 사용합니다.",
            "- 시간 순서 검증, 현재 국내 보험 적용성 및 업무 효과는 입증하지 않았습니다.",
            "- 내부 AI 보조 검토는 외부 인간·보험계리 전문가 검수가 아닙니다.",
        ]
    )
    lines.extend(f"- {_e(item)}" for item in results.get("limitations", []))
    return "\n".join(lines) + "\n"


def _comparison_table(results: dict) -> str:
    metrics = results.get("metrics", {})
    selected = results.get("selected_model")
    rows = []
    for name in _MODELS:
        validation = metrics.get("validation", {}).get(name, {})
        test = metrics.get("test", {}).get(name, {})
        note = '<span class="selection-note">검증 분할에서 선택</span>' if name == selected else ""
        state = ' class="selected"' if name == selected else ""
        rows.append(
            f'<tr{state}><th scope="row">{_e(_MODEL_LABELS[name])}{note}</th>'
            f"<td>{_number(validation.get('mean_poisson_deviance'), 6)}</td>"
            f"<td>{_number(test.get('mean_poisson_deviance'), 6)}</td>"
            f"<td>{_number(test.get('weighted_mae'), 6)}</td>"
            f"<td>{_number(test.get('observed_claims'), 2)} / {_number(test.get('predicted_claims'), 2)}</td>"
            f"<td>{_number(test.get('observed_predicted_ratio'))}</td></tr>"
        )
    return (
        '<div class="table-wrap" tabindex="0" role="region" aria-label="Three-model comparison">'
        '<table id="model-comparison"><caption>세 모델 비교 · Three-model comparison</caption>'
        '<thead><tr><th scope="col">Model</th><th scope="col">Validation deviance ↓</th>'
        '<th scope="col">Test results: deviance ↓</th><th scope="col">Test weighted MAE ↓</th>'
        '<th scope="col">관측 / 예측 청구 건수</th><th scope="col">관측/예측 비율</th></tr></thead>'
        "<tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def _provenance(results: dict) -> str:
    study, provenance = results.get("study", {}), results.get("provenance", {})
    context = {
        "data": {
            key: provenance.get(key)
            for key in ("source_sha256", "source_md5", "source_matches_pinned")
        },
        "original_experiment": {key: provenance.get(key) for key in ("code_sha256", "git_commit")},
        "seed": study.get("seed"),
        "selection_split": study.get("selection_split"),
        "splits": results.get("splits", {}),
        "settings": study.get("settings", {}),
        "environment": results.get("environment", {}),
    }
    return (
        '<details id="provenance"><summary>데이터·코드·seed·split 출처</summary>'
        "<p>아래 코드 해시는 동결 실험의 분석 코드입니다. 현재 표현 renderer의 해시는 별도 presentation manifest에 기록합니다.</p>"
        "<pre>"
        + _e(json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True))
        + "</pre></details>"
    )


def _calibration_table(rows: list[dict]) -> str:
    cells = []
    for row in rows:
        exposure = row.get("exposure")
        try:
            observed = float(row["observed_claims"]) / float(exposure)
            predicted = float(row["predicted_claims"]) / float(exposure)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            observed = predicted = None
        cells.append(
            f'<tr><th scope="row">{_e(row.get("bin", "N/A"))}</th>'
            f"<td>{_integer(row.get('rows'))}</td><td>{_number(exposure, 2)}</td>"
            f"<td>{_number(observed, 6)}</td><td>{_number(predicted, 6)}</td>"
            f"<td>{_number(row.get('observed_claims'), 2)}</td>"
            f"<td>{_number(row.get('predicted_claims'), 2)}</td></tr>"
        )
    return (
        '<div class="table-wrap" tabindex="0" role="region" aria-label="Calibration values">'
        "<table><caption>보정 구간의 실제 값 · 빈도 단위: 청구 / 노출 연수</caption><thead><tr>"
        '<th scope="col">Bin</th><th scope="col">Rows</th><th scope="col">노출 연수</th>'
        '<th scope="col">관측 빈도</th><th scope="col">예측 빈도</th>'
        '<th scope="col">관측 청구</th><th scope="col">예측 청구</th></tr></thead><tbody>'
        + "".join(cells)
        + "</tbody></table></div>"
    )


def _segment_sections(results: dict) -> str:
    dimensions: dict[str, list] = {}
    for row in results.get("segments", []):
        name = str(row.get("segment", "기록 없음"))
        dimensions.setdefault(name, []).append((str(row.get("group", "기록 없음")), row))
    return "".join(
        f'<details class="segment-dimension" open id="segment-dimension-{index}"><summary>'
        + f"{_e(_SEGMENT_LABELS.get(name, name))} · {len(rows)}개 기존 집단</summary>"
        + _metric_table(
            rows,
            f"{_SEGMENT_LABELS.get(name, name)} ({name}) · 선택 모델의 저장된 집단별 오차",
            direction=True,
        )
        + "</details>"
        for index, (name, rows) in enumerate(dimensions.items())
    )


def render_report(results: dict) -> str:
    """Present saved measurements through an automotive-inspired visual study."""
    study, audit = results.get("study", {}), results.get("audit", {})
    provenance = results.get("provenance", {})
    selected = str(results.get("selected_model", "N/A"))
    comparison, calibration = _figures(results)
    comparison = _inline_svg(comparison, "comparison", "Test-set Poisson deviance")
    calibration = _inline_svg(calibration, "calibration", "Observed and predicted calibration")
    interval = _inline_svg(_uncertainty_svg(results), "uncertainty", "Paired deviance difference")
    boot, values = results.get("bootstrap", {}), _interval_values(results)
    if values is None:
        interval_text = '<p class="notice">계산되지 않음: 저장된 구간이 없거나 유효한 수치가 아닙니다. 0 또는 통과 상태로 대체하지 않습니다.</p>'
    else:
        point, lower, upper = values
        interval_text = (
            f"<p>{_e(_MODEL_LABELS.get(selected, selected))} − Training mean · 편차 차이 <strong>{point:.5f}</strong> · 95% 쌍체 구간 "
            f"<strong>[{lower:.5f}, {upper:.5f}]</strong> · 반복 {_integer(boot.get('draws'))}"
            f" · seed {_e(boot.get('seed', 'N/A'))}</p>"
        )
        if selected == "mean":
            interval_text += "<p>기준 모델과 동일한 비교입니다. 개선 효과를 주장하지 않습니다.</p>"
    calibration_rows = results.get("calibration", {}).get(selected, [])
    area_rows = "".join(
        f'<tr><th scope="row">{_e(row.get("area", row.get("Area", "")))}</th>'
        f"<td>{_integer(row.get('rows'))}</td><td>{_number(row.get('exposure'), 2)}</td>"
        f"<td>{_number(row.get('claims'), 2)}</td></tr>"
        for row in results.get("eda", {}).get("by_area", [])
    )
    matched = provenance.get("source_matches_pinned")
    source_state = (
        "원본 바이트 일치"
        if matched is True
        else "원본 일치 확인 없음"
        if matched is False
        else "기록 없음"
    )
    clipped = audit.get("source_values_clipped")
    clipping_state = (
        "자르지 않음" if clipped is False else ("기록상 자름" if clipped is True else "기록 없음")
    )
    limits = [
        _source_description(results),
        "관측 날짜가 없어 시간 순서 검증과 현재 한국 적용성을 입증하지 않았습니다.",
        "보험료·인수·보험금 지급 또는 업무 절감 효과를 검증한 결과가 아닙니다.",
        "내부 AI 보조 검토는 외부 인간·보험계리 전문가 검수가 아닙니다.",
    ]
    limits.extend(str(item) for item in results.get("limitations", []))
    source_prefix = str(provenance.get("source_sha256", "기록 없음"))[:12]
    code_prefix = str(provenance.get("code_sha256", "기록 없음"))[:12]
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MotorClaimLab · 모델 비교 보고서</title><style>
:root {{color-scheme:light; --ink:#102c3b; --muted:#526574; --line:#d5dfe5; --accent:#315bdf; --paper:#f2f5f7; --coral:#ff956d;}}
* {{box-sizing:border-box;}} html {{scroll-padding-top:24px;}} body {{margin:0; color:var(--ink); background:var(--paper); font:16px/1.7 "Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif; -webkit-font-smoothing:antialiased;}}
a {{color:var(--accent); text-underline-offset:4px;}} p {{margin:12px 0; max-width:78ch;}} strong {{font-weight:750;}}
.skip-link {{position:absolute; left:20px; top:-90px; background:white; padding:12px 20px; z-index:2;}} .skip-link:focus {{top:12px;}}
.study-hero {{background:var(--ink); color:white; padding:0 clamp(20px,5vw,72px); border-bottom:6px solid var(--coral);}}
.topbar {{max-width:1280px; margin:auto; min-height:88px; display:flex; align-items:center; justify-content:space-between; gap:20px; border-bottom:1px solid #547383;}}
.wordmark {{display:flex; align-items:center; gap:12px; font-family:Bahnschrift,"Malgun Gothic",sans-serif; font-size:24px; font-weight:700; letter-spacing:-.8px;}}
.lane-mark {{width:29px; height:30px; display:flex; gap:4px; transform:skew(-19deg);}} .lane-mark i {{display:block; width:7px; background:var(--coral);}} .lane-mark i:nth-child(2) {{height:22px; align-self:end;}} .lane-mark i:nth-child(3) {{height:14px; align-self:end;}}
nav {{display:flex; flex-wrap:wrap; gap:4px 22px; font-size:.88rem;}} nav a {{color:#e2edf3; text-decoration:none; padding:10px 0; border-bottom:2px solid transparent;}} nav a:hover {{color:var(--coral); border-color:var(--coral);}}
.hero-frame {{max-width:1280px; margin:auto; display:grid; grid-template-columns:.9fr 1.25fr; align-items:center; gap:36px; padding:60px 0 42px;}}
h1 {{font-size:clamp(2.3rem,4.4vw,4.6rem); line-height:1.23; letter-spacing:-.075em; font-weight:850; margin:0 0 26px; word-break:keep-all;}}
.hero-copy>p {{color:#c4d4dd; max-width:38ch; font-size:.99rem;}} .hero-action {{display:inline-flex; margin-top:20px; padding:11px 22px; color:var(--ink); background:var(--coral); font-weight:750; text-decoration:none; border-radius:5px;}} .hero-action:hover {{background:#ffad8f;}}
.hero-plot {{min-width:0; margin:0;}} .hero-plot figcaption {{color:#c4d4dd; font-size:.82rem; margin:10px 0 0; padding-left:24px; max-width:68ch;}}
.study-context {{max-width:1280px; margin:auto; display:flex; flex-wrap:wrap; gap:10px 30px; padding:22px 0; border-top:1px solid #547383; font-size:.85rem; color:#c4d4dd;}} .study-context strong {{color:white;}}
main {{max-width:1280px; margin:auto; padding:0 clamp(20px,5vw,56px) 48px;}}
section {{padding:48px 0; border-bottom:1px solid var(--line); scroll-margin-top:24px;}}
h2 {{font-size:clamp(1.5rem,2.5vw,2.2rem); line-height:1.4; letter-spacing:-.045em; margin:0 0 16px; word-break:keep-all;}} h3 {{font-size:1.1rem;}}
.section-intro {{display:grid; grid-template-columns:1fr 1.15fr; gap:32px; align-items:start; margin-bottom:24px;}} .section-intro p {{margin:0;}}
.analysis-pair {{display:grid; grid-template-columns:1.05fr 1fr; gap:30px; align-items:center; margin:28px 0; padding:24px; background:white; border-radius:10px; border:1px solid var(--line);}} .analysis-pair figure {{margin:0; min-width:0;}}
.analysis-pair h3 {{margin:0 0 8px;}} .analysis-pair p {{font-size:.87rem; color:var(--muted);}}
.muted,.run-context,footer {{color:var(--muted);}} .run-context {{display:flex; flex-wrap:wrap; gap:6px 22px; font-size:.82rem; margin:12px 0;}}
.table-wrap {{overflow-x:auto; margin:20px 0; background:white; border:1px solid var(--line); border-radius:8px;}} table {{width:100%; min-width:680px; border-collapse:collapse; font-variant-numeric:tabular-nums;}}
caption {{text-align:left; font-weight:650; padding:16px 18px; font-size:.94rem;}} th,td {{padding:14px 16px; border-bottom:1px solid var(--line); vertical-align:middle;}}
th {{text-align:left; font-weight:600;}} td {{text-align:right; white-space:nowrap;}} thead {{background:#eaf0f4; font-size:.8rem; color:#3b5263;}} tbody tr:last-child>* {{border-bottom:0;}}
.selected {{background:#edf2ff;}} .selected th {{border-left:4px solid var(--accent);}} .selection-note {{display:block; margin-top:4px; font-size:.75rem; color:var(--accent); font-weight:600;}}
details {{margin:16px 0; padding:16px 0; border-top:1px solid var(--line);}} summary {{cursor:pointer; font-weight:650; padding:4px 0;}} summary:hover {{color:var(--accent);}}
pre {{overflow-x:auto; background:#e7edf2; padding:18px; font-size:.8rem; border-radius:6px;}} code {{overflow-wrap:anywhere;}}
figure {{margin:24px 0;}} figcaption {{color:var(--muted); font-size:.87rem; margin:10px 0;}} svg {{display:block; width:100%; height:auto;}}
.notice {{border-left:3px solid #986013; padding-left:14px;}} :focus-visible {{outline:3px solid var(--accent); outline-offset:4px;}} .study-hero :focus-visible {{outline-color:var(--coral);}}
.condition-list {{display:grid; grid-template-columns:160px 1fr; gap:16px 24px; padding:24px 0;}} .condition-list dt {{font-weight:700;}} .condition-list dd {{margin:0;}}
#limits {{border-top:3px solid var(--ink);}} li {{margin:10px 0; max-width:85ch;}} footer {{font-size:.8rem; padding-top:28px;}}
@media (max-width:900px) {{.hero-frame {{grid-template-columns:1fr; gap:30px; padding-top:40px;}} .hero-copy>p {{max-width:62ch;}} .hero-plot {{max-width:800px;}} .analysis-pair,.section-intro {{grid-template-columns:1fr; gap:20px;}} .topbar {{align-items:flex-start; flex-direction:column; gap:4px; padding:20px 0 10px;}} h1 {{font-size:clamp(2.3rem,7vw,4rem);}}}}
@media (max-width:520px) {{.study-hero {{padding:0 18px;}} .wordmark {{font-size:22px;}} nav {{gap:2px 17px; font-size:.8rem;}} .hero-frame {{padding:32px 0; gap:24px;}} .hero-plot figcaption {{padding-left:0;}} .study-context {{gap:8px 18px; font-size:.78rem;}} main {{padding:0 18px 32px;}} section {{padding:34px 0;}} .analysis-pair {{padding:12px; gap:12px;}} .condition-list {{grid-template-columns:1fr; gap:6px;}} .condition-list dd {{margin-bottom:14px;}}}}
.segment-review {{margin:32px 0; padding:24px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line);}} .segment-review>h3 {{margin-top:0;}} .segment-review>p {{font-size:.91rem;}} .segment-review-row {{padding:22px 0; border-top:1px solid var(--line);}} .segment-review-row h4 {{margin:0 0 8px; font-size:1rem;}} .segment-review-row p {{font-size:.88rem; margin:8px 0; overflow-wrap:anywhere;}} .review-support {{color:var(--muted);}} .review-gap {{display:grid; grid-template-columns:1fr 1fr; gap:20px; margin:16px 0; font-variant-numeric:tabular-nums;}} .review-gap dt {{font-size:.82rem; color:var(--muted);}} .review-gap dd {{margin:5px 0 0; font-size:1.35rem; font-weight:700;}} .review-unavailable {{color:#684f25;}} .segment-review a:focus-visible {{outline:3px solid var(--accent); outline-offset:5px;}} .segment-dimension:target>summary {{background:#e8edf8; outline:2px solid var(--accent); outline-offset:4px;}} .segment-review ::selection {{background:#ced8fa; color:var(--ink);}}
@media (max-width:520px) {{.review-gap {{grid-template-columns:1fr; gap:14px;}} .segment-review {{padding:18px 0;}}}}
@media (prefers-reduced-motion:reduce) {{*,*::before,*::after {{animation:none!important; transition:none!important; scroll-behavior:auto!important;}}}}
@media print {{body {{background:white; font-size:10pt;}} .skip-link,nav,.hero-action {{display:none;}} .study-hero {{print-color-adjust:exact; -webkit-print-color-adjust:exact;}} .hero-frame {{grid-template-columns:1fr 1fr; padding:24px 0;}} h1 {{font-size:25pt;}} main {{padding:0;}} .analysis-pair,.section-intro {{display:block;}} section {{padding:20px 0;}} .table-wrap {{overflow:visible; border:0;}} table {{min-width:0; font-size:8pt;}} th,td {{padding:5px; white-space:normal;}} details>pre {{display:block;}} figure,tr {{break-inside:avoid;}}}}
</style></head><body><a class="skip-link" href="#report-content">분석 본문으로 건너뛰기</a>
<header class="study-hero"><div class="topbar"><div class="wordmark"><span class="lane-mark" aria-hidden="true"><i></i><i></i><i></i></span>MotorClaimLab</div><nav aria-label="보고서 구간"><a href="#selection">모델 비교</a><a href="#uncertainty">불확실성</a><a href="#calibration">보정과 오차</a><a href="#provenance">출처</a></nav></div>
<div class="hero-frame"><div class="hero-copy"><h1>청구 건수 너머,<br>위험을 읽는 방법.</h1><p>가입 기간이 다른 계약을 어떻게 비교할까요? 노출 기간을 반영한 세 모델의 예측과, 평균 오차 뒤에 남은 과소·과대예측을 살펴봅니다.</p><p>{_e(_source_description(results))} 현재 국내 보험 업무의 적합성 또는 효과를 입증하지 않았습니다.</p><a class="hero-action" href="#selection">세 모델의 결과 비교하기</a></div>
<figure class="hero-plot">{calibration}<figcaption>예측 순위별 관측(실선·원)과 예측(파선·사각형). 청구 / 노출 연수. 가로축은 시간 흐름이 아닌 예측 순위입니다. <a href="#calibration" style="color:#ff956d">보정 구간의 실제 값 보기</a></figcaption></figure></div>
<div class="study-context"><span><strong>{_integer(study.get("rows"))}</strong> 계약 행</span><span>분석 노출 <strong>{_number(_study_exposure(results), 2)}</strong>년</span><span>{"전체 자료 실행" if study.get("sampled") is False else ("표본 실행" if study.get("sampled") is True else "표본 여부 기록 없음")}</span><span>{_e(study.get("data_kind", "기록 없음"))} / seed {_e(study.get("seed", "기록 없음"))}</span></div></header>
<main id="report-content" tabindex="-1"><section aria-labelledby="selection"><div class="section-intro"><h2 id="selection">어떤 모델이<br>얼마나 덜 틀렸을까?</h2>
<p>선택 모델: <strong>{_e(_MODEL_LABELS.get(selected, selected))}</strong> (<code>{_e(selected)}</code>). 모델 선택에는 <strong>{_e(study.get("selection_split", "기록 없음"))}</strong> 분할만 사용했습니다. Test results는 선택 이후 평가입니다.</p>
</div><figure><figcaption>같은 테스트 자료, 같은 노출 가중 기준. 낮은 편차는 이 분할에서 더 작은 예측 오차를 뜻합니다.</figcaption>{comparison}</figure>
{_comparison_table(results)}
<p class="muted">편차와 가중 MAE는 낮을수록 작게 틀립니다. 관측/예측 비율 1은 합계 일치이며, 집단별 보정이나 조건검사 통과를 의미하지 않습니다.</p>
<div class="run-context"><span>Data <code>{_e(source_prefix)}</code></span><span>Analysis code <code>{_e(code_prefix)}</code></span><span>Renderer {RENDERER_VERSION}</span></div>
{_provenance(results)}
</section>
<section aria-labelledby="uncertainty"><h2 id="uncertainty">차이는 얼마나 확실할까?</h2>{interval_text}
<div class="analysis-pair"><figure>{interval}<figcaption>선택 모델 − 평균 기준. 하나의 쌍체 차이 구간이며 모델별 오차막대가 아닙니다.</figcaption></figure><div><h3>0을 기준으로 읽는 비교</h3><p>0은 편차 차이 없음, 음수는 선택 모델에 유리합니다. 같은 정책 인덱스로 재표집한 구간입니다.</p><p>현재 분할과 이미 적합된 모델(frozen fits)에 조건부이며, 재학습·자료 수집·미래 시점의 불확실성을 포함하지 않습니다.</p></div></div></section>
<section aria-labelledby="calibration"><div class="section-intro"><h2 id="calibration">평균이 좋아져도,<br>오차는 남습니다.</h2><p>첫 화면의 관측·예측 곡선을 실제 값으로 확인합니다. 선택 모델을 예측 순위로 나눈 구간과, 연령·차량·지역 집단의 오차를 함께 읽으세요. 합계가 비슷하더라도 구간마다 과소·과대예측이 남을 수 있습니다.</p></div>
{_calibration_table(calibration_rows)}
<h3>차원별 집단 오차 탐색</h3><p>아래 펼침 항목에서 운전자 연령·차량 연령·지역을 비교하세요. 각 표는 선택 모델 <strong>{_e(_MODEL_LABELS.get(selected, selected))}</strong>의 저장된 집단만 보여줍니다. 행 수·노출량·관측/예측 청구를 함께 읽으며, 교차 집단·다른 모델의 집단별 결과·인과 설명을 뜻하지 않습니다.</p>
<p>관측/예측 비율이 1보다 크면 이 집단에서 과소예측, 1보다 작으면 과대예측입니다. 비율이 없으면 N/A로 표시합니다. Sparse는 행 수 50개 미만 또는 노출 합계 10년 미만을 뜻합니다. 각 행의 표시는 유지하며, 해당 구간의 불확실성에 주의합니다.</p>
<p>청구 건수의 기술적 차이: 관측 − 예측이 양수면 과소예측, 음수면 과대예측입니다. 인과 설명·보험금 판단·유의성 판정이 아닙니다. 표시된 두 자리에서 같아 보여도 차이의 부호는 저장된 원래 값에서 계산합니다.</p>
{_segment_review_html(results)}
{_segment_sections(results)}</section>
<section aria-labelledby="conditions"><h2 id="conditions">관측 지표와 기록된 조건의 구분</h2>
<p>위 숫자는 측정값입니다. 아래는 저장된 메타데이터의 조건 기록이며 승인·규제 적합성 점수로 바꾸지 않습니다.</p>
<p>전체 입력 감사: {_integer(audit.get("rows"))}행 · 노출 {_number(audit.get("exposure"), 2)}년. 표본 실행에서는 위 분석 대상의 행 수·노출 합계와 구분합니다.</p>
<dl class="condition-list"><dt>입력 식별</dt><dd>{_e(source_state)}. 원본 권리·수집 경위의 독립 검증과는 별개입니다.</dd>
<dt>유효 관측 처리</dt><dd>{_e(clipping_state)} · 노출 1년 초과 {_integer(audit.get("exposure_gt_one"))}행 · 청구 4건 초과 {_integer(audit.get("claims_gt_four"))}행.</dd></dl>
<div class="table-wrap" tabindex="0" role="region" aria-label="Area descriptive values"><table><caption>Descriptive Area aggregates</caption><thead><tr><th scope="col">Area</th><th scope="col">Rows</th><th scope="col">노출 연수</th><th scope="col">관측 청구</th></tr></thead><tbody>{area_rows}</tbody></table></div></section>
<section aria-labelledby="limits"><h2 id="limits">해석 범위</h2><ul>{"".join(f"<li>{_e(item)}</li>" for item in limits)}</ul></section>
<footer>MotorClaimLab · renderer {RENDERER_VERSION} · Python {_e(results.get("environment", {}).get("python", "기록 없음"))} · 출처: 저장된 집계 결과. 이 표현을 만들기 위한 재학습·재평가는 없습니다.</footer>
</main></body></html>"""
