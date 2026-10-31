"""Offline aggregate HTML, Markdown, and SVG reporting."""

# Long HTML template lines are kept intact so the markup remains easy to scan.
# ruff: noqa: E501

from __future__ import annotations

import html
import json
import math
import re
from io import StringIO
from pathlib import Path
from typing import Any

from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure

_MODELS = ("mean", "poisson_glm", "poisson_hgb")
RENDERER_VERSION = "2.0"
_MODEL_LABELS = {
    "mean": "Training mean",
    "poisson_glm": "Poisson GLM",
    "poisson_hgb": "Poisson HGB",
}


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


def _source_description(results: dict) -> str:
    pinned = (
        results.get("study", {}).get("data_kind") == "openml_pinned"
        and results.get("provenance", {}).get("source_matches_pinned") is True
    )
    if pinned:
        return "과거 프랑스 자료에 대한 공개 데이터 실험입니다."
    return "로컬 입력 자료에 대한 실험입니다. 자료의 출처와 실제·합성 여부는 확인하지 않았습니다."


def _metric_table(rows: list[tuple[str, dict]], caption: str) -> str:
    body = "".join(
        "<tr>"
        + f"<th scope='row'>{_e(label + (' · Sparse' if metric.get('sparse') else ''))}</th>"
        + f"<td>{_integer(metric.get('rows'))}</td>"
        + f"<td>{_number(metric.get('exposure'), 2)}</td>"
        + f"<td>{_number(metric.get('mean_poisson_deviance'))}</td>"
        + f"<td>{_number(metric.get('weighted_mae'))}</td>"
        + f"<td>{_number(metric.get('observed_claims'), 2)}</td>"
        + f"<td>{_number(metric.get('predicted_claims'), 2)}</td>"
        + f"<td>{_number(metric.get('observed_predicted_ratio'))}</td></tr>"
        for label, metric in rows
    )
    return (
        f"<div class='table-wrap' tabindex='0' role='region' aria-label='{_e(caption)}'><table><caption>{_e(caption)}</caption>"
        "<thead><tr><th scope='col'>Model / group</th><th scope='col'>Rows</th>"
        "<th scope='col'>Exposure (years)</th><th scope='col'>Poisson deviance</th>"
        "<th scope='col'>Weighted MAE</th><th scope='col'>Observed claims</th>"
        "<th scope='col'>Predicted claims</th><th scope='col'>Observed / predicted</th>"
        f"</tr></thead><tbody>{body}</tbody></table></div>"
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
    figure = Figure(figsize=(8.2, 2.5), layout="constrained")
    axis = figure.subplots()
    values = _interval_values(results)
    if values is None:
        axis.text(0.5, 0.5, "Interval unavailable (not computed)", ha="center", va="center")
        axis.set_axis_off()
    else:
        point, lower, upper = values
        zero = axis.axvline(0, color="#596574", linewidth=1.2, linestyle="--")
        zero.set_gid("zero-reference")
        interval = axis.hlines(0.5, lower, upper, colors="#16727c", linewidth=4)
        interval.set_gid("paired-ci")
        axis.vlines([lower, upper], 0.44, 0.56, colors="#16727c", linewidth=1.4)
        (marker,) = axis.plot(point, 0.5, marker="D", color="#152b40", markersize=7)
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
            "Paired deviance difference · Frozen fits and split", loc="left", fontsize=11
        )
        axis.grid(axis="x", alpha=0.18)
        for name in ("top", "right", "left"):
            axis.spines[name].set_visible(False)
    svg = _figure_svg(figure, "paired-difference")
    if directory is not None:
        figure.savefig(directory / "paired-difference.png", dpi=160)
    figure.clear()
    return svg


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
    bars = axis.bar(
        [_MODEL_LABELS[name] for name in _MODELS],
        plot_vals,
        color=[
            "#16727c" if name == results.get("selected_model") else "#9aa8b5" for name in _MODELS
        ],
    )
    axis.set_title("Test-set Poisson deviance")
    axis.set_ylabel("Exposure-weighted deviance")
    axis.grid(axis="y", alpha=0.22)
    axis.set_axisbelow(True)
    for bar, value in zip(bars, vals, strict=True):
        axis.annotate(
            _number(value),
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=9,
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
    calibration = Figure(figsize=(8.2, 4.2), layout="constrained")
    axis = calibration.subplots()
    positions = list(range(len(labels)))
    axis.plot(positions, observed_rates, marker="o", color="#087e8b", label="Observed rate")
    axis.plot(
        positions,
        predicted_rates,
        marker="s",
        linestyle="--",
        color="#c76d3a",
        label="Predicted rate",
    )
    for x, value in zip(positions, observed_rates, strict=True):
        if not math.isfinite(value):
            continue
        axis.annotate(
            _number(value, 3),
            (x, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    for x, value in zip(positions, predicted_rates, strict=True):
        if not math.isfinite(value):
            continue
        axis.annotate(
            _number(value, 3),
            (x, value),
            xytext=(0, -14),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    axis.set_xticks(positions, labels)
    axis.set_title(f"Calibration by prediction bin — {_MODEL_LABELS.get(selected, selected)}")
    axis.set_xlabel("Prediction bin")
    axis.set_ylabel("Claim frequency (claims / exposure year)")
    axis.grid(alpha=0.22)
    axis.legend(frameon=False)
    if incomplete_bins:
        axis.text(
            0.02,
            0.95,
            "Incomplete calibration bins: " + ", ".join(incomplete_bins),
            transform=axis.transAxes,
            va="top",
            fontsize=9,
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
            f"선택 − 평균 기준: **{point:.5f}**; 95% paired interval **[{lower:.5f}, {upper:.5f}]**."
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
            "| Segment / group | Rows | Exposure | Poisson deviance | Observed / predicted |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in results.get("segments", []):
        label = f"{row.get('segment', '')}: {row.get('group', '')}"
        if row.get("sparse"):
            label += " · Sparse"
        label = _e(label).replace("|", "&#124;").replace("\n", " ")
        lines.append(
            f"| {label} | {_integer(row.get('rows'))} | {_number(row.get('exposure'), 2)} | "
            f"{_number(row.get('mean_poisson_deviance'))} | {_number(row.get('observed_predicted_ratio'))} |"
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


def render_report(results: dict) -> str:
    """Render saved measurements and their provenance as a restrained research document."""
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
            f"<p>편차 차이 <strong>{point:.5f}</strong> · 95% 쌍체 구간 "
            f"<strong>[{lower:.5f}, {upper:.5f}]</strong> · 반복 {_integer(boot.get('draws'))}"
            f" · seed {_e(boot.get('seed', 'N/A'))}</p>"
        )
        if selected == "mean":
            interval_text += "<p>기준 모델과 동일한 비교입니다. 개선 효과를 주장하지 않습니다.</p>"
    segments = [
        (f"{row.get('segment', '')}: {row.get('group', '')}", row)
        for row in results.get("segments", [])
    ]
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
:root {{color-scheme:light; --ink:#1d2938; --muted:#526171; --line:#d8dfe6; --accent:#176c77;}}
* {{box-sizing:border-box;}} body {{margin:0; color:var(--ink); background:#fff; font:15px/1.6 system-ui,"Segoe UI",sans-serif;}}
main {{max-width:1120px; margin:auto; padding:28px clamp(16px,4vw,40px) 48px;}}
header {{border-bottom:1px solid var(--line); padding-bottom:18px;}} h1 {{font-size:clamp(1.5rem,3vw,2rem); margin:8px 0; line-height:1.25;}}
h2 {{font-size:1.15rem; margin:0 0 12px;}} h3 {{font-size:1rem;}} section {{padding:26px 0; border-bottom:1px solid var(--line);}}
p {{margin:10px 0;}} .muted,.run-context,footer {{color:var(--muted);}} .run-context {{display:flex; flex-wrap:wrap; gap:6px 22px; font-size:.9rem;}}
nav {{display:flex; flex-wrap:wrap; gap:18px; font-size:.9rem;}} a {{color:var(--accent); text-underline-offset:3px;}}
.table-wrap {{overflow-x:auto; margin:12px 0 18px;}} table {{width:100%; min-width:680px; border-collapse:collapse; font-variant-numeric:tabular-nums;}}
caption {{text-align:left; font-weight:600; margin-bottom:8px;}} th,td {{padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top;}}
th {{text-align:left; font-weight:600;}} td {{text-align:right; white-space:nowrap;}} thead {{background:#f4f6f8; font-size:.87rem;}}
.selected {{background:#f0f7f8;}} .selected th {{border-left:3px solid var(--accent);}} .selection-note {{display:block; font-size:.78rem; color:var(--accent); font-weight:500;}}
details {{margin:14px 0; padding:10px 0; border-top:1px solid var(--line);}} summary {{cursor:pointer; font-weight:600;}}
pre {{overflow-x:auto; background:#f6f7f9; padding:14px; font-size:.82rem;}} code {{overflow-wrap:anywhere;}}
figure {{margin:14px 0;}} figcaption {{color:var(--muted); font-size:.9rem;}} svg {{display:block; width:100%; height:auto;}}
.notice {{border-left:3px solid #8e6d37; padding-left:12px;}} :focus-visible {{outline:2px solid var(--accent); outline-offset:3px;}}
footer {{font-size:.85rem; padding-top:22px;}} li {{margin:5px 0;}} .condition-list dt {{font-weight:600;}} .condition-list dd {{margin:0 0 10px;}}
</style></head><body><main>
<header><nav aria-label="보고서 구간"><a href="#selection">모델 비교</a><a href="#uncertainty">불확실성</a><a href="#calibration">보정과 오차</a><a href="#provenance">출처</a></nav>
<h1>자동차보험 청구 빈도 · 모델 비교</h1><p class="muted">{_e(_source_description(results))} 현재 국내 보험 업무의 적합성 또는 효과를 입증하지 않았습니다.</p>
<div class="run-context"><span>{_integer(study.get("rows"))}행 · {_e(study.get("data_kind", "기록 없음"))}</span><span>{"표본 실행" if study.get("sampled") is True else ("전체 자료 실행" if study.get("sampled") is False else "표본 여부 기록 없음")}</span><span>노출 {_number(audit.get("exposure"), 2)}년</span><span>seed {_e(study.get("seed", "기록 없음"))}</span></div>
<div class="run-context"><span>Data <code>{_e(source_prefix)}</code></span><span>Analysis code <code>{_e(code_prefix)}</code></span><span>Renderer {RENDERER_VERSION}</span></div></header>
<section aria-labelledby="selection"><h2 id="selection">세 모델 비교</h2>
<p>선택 모델: <strong>{_e(selected)}</strong>. 모델 선택에는 <strong>{_e(study.get("selection_split", "기록 없음"))}</strong> 분할만 사용했습니다. Test results는 선택 이후 평가입니다.</p>
{_comparison_table(results)}
<p class="muted">편차와 가중 MAE는 낮을수록 작게 틀립니다. 관측/예측 비율 1은 합계 일치이며, 집단별 보정이나 조건검사 통과를 의미하지 않습니다.</p>
{_provenance(results)}
<details><summary>Test-set Poisson deviance 차트</summary><figure><figcaption>노출 가중 포아송 편차 · 낮을수록 작음</figcaption>{comparison}</figure></details></section>
<section aria-labelledby="uncertainty"><h2 id="uncertainty">선택 모델 − 평균 기준 · 쌍체 불확실성</h2>{interval_text}
<figure><figcaption>0은 편차 차이 없음, 음수는 선택 모델에 유리합니다. 하나의 쌍체 차이 구간이며 모델별 오차막대가 아닙니다.</figcaption>{interval}</figure>
<p class="muted">같은 정책 인덱스로 재표집한 구간입니다. 현재 분할과 이미 적합된 모델(frozen fits)에 조건부이며, 재학습·자료 수집·미래 시점의 불확실성을 포함하지 않습니다.</p></section>
<section aria-labelledby="calibration"><h2 id="calibration">실측·예측 보정과 집단별 오차</h2>
<figure><figcaption>예측 순위별 관측(실선·원)과 예측(파선·사각형). 단위는 청구 / 노출 연수입니다.</figcaption>{calibration}</figure>
{_calibration_table(calibration_rows)}
<p>Sparse: 행 수 50개 미만 또는 노출 합계 10년 미만. 각 행의 표시는 유지하며, 해당 구간의 불확실성에 주의합니다.</p>
{_metric_table(segments, "Selected-model segment errors; sparse groups need caution")}</section>
<section aria-labelledby="conditions"><h2 id="conditions">관측 지표와 기록된 조건의 구분</h2>
<p>위 숫자는 측정값입니다. 아래는 저장된 메타데이터의 조건 기록이며 승인·규제 적합성 점수로 바꾸지 않습니다.</p>
<dl class="condition-list"><dt>입력 식별</dt><dd>{_e(source_state)}. 원본 권리·수집 경위의 독립 검증과는 별개입니다.</dd>
<dt>유효 관측 처리</dt><dd>{_e(clipping_state)} · 노출 1년 초과 {_integer(audit.get("exposure_gt_one"))}행 · 청구 4건 초과 {_integer(audit.get("claims_gt_four"))}행.</dd></dl>
<div class="table-wrap" tabindex="0" role="region" aria-label="Area descriptive values"><table><caption>Descriptive Area aggregates</caption><thead><tr><th scope="col">Area</th><th scope="col">Rows</th><th scope="col">노출 연수</th><th scope="col">관측 청구</th></tr></thead><tbody>{area_rows}</tbody></table></div></section>
<section aria-labelledby="limits"><h2 id="limits">해석 범위</h2><ul>{"".join(f"<li>{_e(item)}</li>" for item in limits)}</ul></section>
<footer>MotorClaimLab · renderer {RENDERER_VERSION} · Python {_e(results.get("environment", {}).get("python", "기록 없음"))} · 출처: 저장된 집계 결과. 이 표현을 만들기 위한 재학습·재평가는 없습니다.</footer>
</main></body></html>"""
