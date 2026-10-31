"""Offline aggregate HTML, Markdown, and SVG reporting."""

# Long HTML template lines are kept intact so the markup remains easy to scan.
# ruff: noqa: E501

from __future__ import annotations

import html
import math
from io import StringIO
from pathlib import Path
from typing import Any

from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure

_MODELS = ("mean", "poisson_glm", "poisson_hgb")
_MODEL_LABELS = {
    "mean": "Training mean",
    "poisson_glm": "Poisson GLM",
    "poisson_hgb": "Poisson HGB",
}


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
        f"<div class='table-wrap'><table><caption>{_e(caption)}</caption>"
        "<thead><tr><th scope='col'>Model / group</th><th scope='col'>Rows</th>"
        "<th scope='col'>Exposure (years)</th><th scope='col'>Poisson deviance</th>"
        "<th scope='col'>Weighted MAE</th><th scope='col'>Observed claims</th>"
        "<th scope='col'>Predicted claims</th><th scope='col'>Observed / predicted</th>"
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _figure_svg(figure: Figure) -> str:
    output = StringIO()
    FigureCanvasSVG(figure).print_svg(output)
    value = output.getvalue()
    return value[value.find("<svg") :]


def _figures(results: dict, directory: Path | None = None) -> tuple[str, str]:
    import matplotlib

    matplotlib.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    comparison = Figure(figsize=(8.2, 4.2), layout="constrained")
    axis = comparison.subplots()
    metrics = results.get("metrics", {}).get("test", {})
    vals = [metrics.get(name, {}).get("mean_poisson_deviance") for name in _MODELS]
    plot_vals = [float(v) if v is not None and math.isfinite(float(v)) else 0 for v in vals]
    bars = axis.bar(
        [_MODEL_LABELS[name] for name in _MODELS],
        plot_vals,
        color=["#53657d", "#087e8b", "#c76d3a"],
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
    comparison_svg = _figure_svg(comparison)
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
    for bin_number in bins:
        group = by_bin[bin_number]
        exposure = math.fsum(float(row.get("exposure", 0)) for row in group)
        observed = math.fsum(float(row.get("observed_claims", 0)) for row in group)
        predicted = math.fsum(float(row.get("predicted_claims", 0)) for row in group)
        if exposure > 0:
            labels.append(str(bin_number))
            observed_rates.append(observed / exposure)
            predicted_rates.append(predicted / exposure)
    calibration = Figure(figsize=(8.2, 4.2), layout="constrained")
    axis = calibration.subplots()
    positions = list(range(len(labels)))
    axis.plot(positions, observed_rates, marker="o", color="#087e8b", label="Observed rate")
    axis.plot(positions, predicted_rates, marker="s", color="#c76d3a", label="Predicted rate")
    for x, value in zip(positions, observed_rates, strict=True):
        axis.annotate(
            _number(value, 3),
            (x, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    for x, value in zip(positions, predicted_rates, strict=True):
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
    calibration_svg = _figure_svg(calibration)
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
    """Render a portable Markdown summary containing aggregates only."""
    study = results.get("study", {})
    lines = [
        "# MotorClaimLab frequency study",
        "",
        _source_description(results)
        + " 현재 한국 시장의 성능이나 보험 업무 효과를 입증하지 않았습니다.",
        "",
        f"- Selected model: {_e(results.get('selected_model', 'N/A'))} "
        f"(selected on {_e(study.get('selection_split', 'N/A'))})",
        f"- Data kind: {_e(study.get('data_kind', 'N/A'))}; rows: {_integer(study.get('rows'))}; "
        f"sampled: {study.get('sampled', 'N/A')}",
        "",
        "## Test results",
        "",
        "| Model | Rows | Exposure | Poisson deviance | Weighted MAE | Observed claims | Predicted claims | Ratio |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    metrics = results.get("metrics", {}).get("test", {})
    for name in _MODELS:
        metric = metrics.get(name, {})
        lines.append(
            f"| {_MODEL_LABELS[name]} | {_integer(metric.get('rows'))} | "
            f"{_number(metric.get('exposure'), 2)} | "
            f"{_number(metric.get('mean_poisson_deviance'))} | "
            f"{_number(metric.get('weighted_mae'))} | "
            f"{_number(metric.get('observed_claims'), 2)} | "
            f"{_number(metric.get('predicted_claims'), 2)} | "
            f"{_number(metric.get('observed_predicted_ratio'))} |"
        )
    lines.extend(["", "## Validation results", "", "| Model | Poisson deviance |", "|---|---:|"])
    for name, metric in results.get("metrics", {}).get("validation", {}).items():
        lines.append(
            f"| {_e(_MODEL_LABELS.get(name, name))} | "
            f"{_number(metric.get('mean_poisson_deviance'))} |"
        )
    lines.extend(
        [
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
        lines.append(
            f"| {_e(label)} | {_integer(row.get('rows'))} | "
            f"{_number(row.get('exposure'), 2)} | "
            f"{_number(row.get('mean_poisson_deviance'))} | "
            f"{_number(row.get('observed_predicted_ratio'))} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- 빈도는 청구 건수를 관측 노출 연수로 나눈 값이며 성과 지표는 노출 가중치를 사용합니다.",
            "- 차이는 고정된 적합 모델과 분할을 조건으로 한 쌍체 부트스트랩이며 재학습 불확실성을 나타내지 않습니다.",
            "- 자료에 신뢰할 만한 날짜가 없어 시간 순서 검증과 현재 한국 적용성을 주장하지 않습니다.",
            "- 내부 AI 보조 검토는 독립된 보험계리사 또는 전문가 검토가 아닙니다.",
        ]
    )
    for item in results.get("limitations", []):
        lines.append(f"- {_e(item)}")
    return "\n".join(lines) + "\n"


def render_report(results: dict) -> str:
    """Render a self-contained, accessible Korean HTML report with inline SVG."""
    study = results.get("study", {})
    metrics = results.get("metrics", {})
    audit = results.get("audit", {})
    comparison_svg, calibration_svg = _figures(results)
    split_rows = []
    for name in ("train", "validation", "test"):
        split = results.get("splits", {}).get(name, {})
        split_rows.append(
            (name.title(), {"rows": split.get("rows"), "exposure": split.get("exposure")})
        )
    split_table = (
        "<div class='table-wrap'><table><caption>Data split summary</caption>"
        "<thead><tr><th scope='col'>Split</th><th scope='col'>Rows</th>"
        "<th scope='col'>Exposure (years)</th></tr></thead><tbody>"
        + "".join(
            f"<tr><th scope='row'>{label}</th>"
            f"<td>{_integer(row['rows'])}</td>"
            f"<td>{_number(row['exposure'], 2)}</td></tr>"
            for label, row in split_rows
        )
        + "</tbody></table></div>"
    )
    test_rows = [(_MODEL_LABELS[name], metrics.get("test", {}).get(name, {})) for name in _MODELS]
    validation_rows = [
        (_MODEL_LABELS.get(name, name), value)
        for name, value in metrics.get("validation", {}).items()
    ]
    segments = []
    for row in results.get("segments", []):
        label = f"{row.get('segment', '')}: {row.get('group', '')}"
        segments.append((label, row))
    calibration_entries = results.get("calibration", {}).get(
        str(results.get("selected_model", "")), []
    )
    calibration_table = _metric_table(
        [(f"Bin {row.get('bin', '')}", row) for row in calibration_entries],
        "Selected-model calibration bins (aggregate counts / exposure)",
    )
    boot = results.get("bootstrap", {})
    limitations = [
        _source_description(results) + " 시간 순서 검증이나 현재 한국 적합성을 보여주지 않습니다.",
        "이 결과는 보험료 산정, 인수, 보험금 지급에 사용할 수 없으며 업무 절감이나 사업 성과를 측정하지 않았습니다.",
        "부트스트랩 구간은 고정 분할과 이미 적합한 모델을 조건으로 합니다. 재학습 불확실성을 포함하지 않습니다.",
        "내부 AI 보조 검토는 독립된 외부 전문가 검토가 아닙니다.",
    ]
    limitations.extend(str(value) for value in results.get("limitations", []))
    eda = results.get("eda", {})
    eda_rows = []
    for row in eda.get("by_area", []):
        eda_rows.append(
            (
                str(row.get("area", row.get("Area", ""))),
                {
                    "rows": row.get("rows"),
                    "exposure": row.get("exposure"),
                    "observed_claims": row.get("claims"),
                },
            )
        )
    area_table = (
        "<div class='table-wrap'><table><caption>Descriptive Area aggregates</caption>"
        "<thead><tr><th scope='col'>Area</th><th scope='col'>Rows</th>"
        "<th scope='col'>Exposure (years)</th><th scope='col'>Observed claims</th>"
        "</tr></thead><tbody>"
        + "".join(
            f"<tr><th scope='row'>{_e(label)}</th>"
            f"<td>{_integer(row['rows'])}</td>"
            f"<td>{_number(row['exposure'], 2)}</td>"
            f"<td>{_number(row['observed_claims'], 2)}</td></tr>"
            for label, row in eda_rows
        )
        + "</tbody></table></div>"
    )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MotorClaimLab | 빈도 분석 보고서</title>
<style>
:root {{ color-scheme: light; --ink:#182536; --muted:#526174; --line:#d9e1e9; --panel:#f4f7fa; --accent:#087e8b; }}
* {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); font:16px/1.6 system-ui,"Segoe UI",sans-serif; background:#edf2f6; }}
main {{ max-width:1120px; margin:auto; padding:clamp(18px,4vw,48px); background:white; }}
h1,h2,h3 {{ line-height:1.25; }} h1 {{ font-size:clamp(2rem,5vw,3.2rem); margin:.2em 0; }}
h2 {{ margin-top:2.2em; padding-bottom:.4em; border-bottom:1px solid var(--line); }}
.eyebrow {{ color:var(--accent); font-weight:700; letter-spacing:.06em; }} .lede,.muted {{ color:var(--muted); }}
.notice {{ border-left:5px solid #c76d3a; padding:16px 20px; background:#fff6ef; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; }}
.card {{ padding:16px; background:var(--panel); border-radius:10px; }} .card strong {{ display:block; font-size:1.35rem; }}
.table-wrap {{ overflow-x:auto; margin:14px 0 22px; }} table {{ width:100%; border-collapse:collapse; min-width:760px; font-variant-numeric:tabular-nums; }}
caption {{ text-align:left; font-weight:700; padding:8px 0; }} th,td {{ text-align:left; padding:9px 11px; border-bottom:1px solid var(--line); }}
thead {{ background:var(--panel); }} svg {{ display:block; width:100%; height:auto; margin:12px 0 26px; }}
li {{ margin:.4em 0; }} footer {{ margin-top:3em; color:var(--muted); border-top:1px solid var(--line); padding-top:16px; }}
</style></head><body><main>
<header><div class="eyebrow">재현 가능한 교육용 연구</div><h1>자동차보험 청구 빈도 모델 비교</h1>
<p class="lede">노출 기간을 반영해 단순 평균, 포아송 회귀, 부스팅 모델의 오류와 보정 상태를 살펴봅니다.</p>
<p class="notice"><strong>해석 범위:</strong> {_e(_source_description(results))} 현재 한국 시장의 타당성, 보험사 업무 효과 또는 보험 의사결정을 검증하지 않았습니다.</p></header>
<section aria-labelledby="overview"><h2 id="overview">실험 개요</h2><div class="cards">
<div class="card">선택 모델<strong>{_e(results.get("selected_model", "N/A"))}</strong><span class="muted">선택 기준: {_e(study.get("selection_split", "N/A"))}</span></div>
<div class="card">관측 행<strong>{_integer(study.get("rows"))}</strong><span class="muted">표본 실행: {_e(study.get("sampled", "N/A"))}</span></div>
<div class="card">자료 상태<strong>{_e(study.get("data_kind", "N/A"))}</strong><span class="muted">seed: {_e(study.get("seed", "N/A"))}</span></div>
<div class="card">감사 행<strong>{_integer(audit.get("rows"))}</strong><span class="muted">청구 {_integer(audit.get("claims"))}건 · 노출 {_number(audit.get("exposure"), 2)}년</span></div>
</div>{split_table}</section>
<section aria-labelledby="selection"><h2 id="selection">모델 선택과 평가</h2>
<p>모델 선택은 검증 분할의 노출 가중 포아송 편차로 수행했습니다. 아래 테스트 분할 결과는 선택 이후의 평가이며, 이 점수로 선택이나 설정을 바꾸지 않았습니다.</p>
{_metric_table(validation_rows, "Validation results — used for model selection")}
{_metric_table(test_rows, "Test results — held out for final evaluation")}
<figure><figcaption>테스트 세트 포아송 편차. 낮을수록 관측 빈도와 예측 빈도의 차이가 작습니다.</figcaption>{comparison_svg}</figure></section>
<section aria-labelledby="calibration"><h2 id="calibration">보정과 집단별 오차</h2>
<p>보정 빈도는 각 bin의 청구 건수 합계를 노출 합계로 나누어 계산합니다. 빈도 평균들의 단순 평균은 사용하지 않습니다.</p>
<figure><figcaption>선택 모델의 예측 순위별 관측 및 예측 청구 빈도</figcaption>{calibration_svg}</figure>
{calibration_table}
<p>Sparse 표시는 행 수가 50개 미만이거나 노출 합계가 10년 미만인 구간입니다. 해당 구간은 관측 불확실성에 주의해 해석합니다.</p>
{_metric_table(segments, "Selected-model segment errors; sparse groups need caution")}</section>
<section aria-labelledby="uncertainty"><h2 id="uncertainty">불확실성과 데이터 감사</h2>
<p>선택 모델 − 기준 모델 테스트 편차 차이: <strong>{_number(boot.get("selected_minus_baseline"))}</strong>; 95% 쌍체 부트스트랩 구간 [{_number(boot.get("ci_lower"))}, {_number(boot.get("ci_upper"))}], 반복 {_integer(boot.get("draws"))}, seed {_e(boot.get("seed", "N/A"))}. 음수는 선택 모델에 유리합니다. 구간은 고정된 적합 모델과 분할을 조건으로 계산합니다.</p>
<p>노출 1년 초과 행: {_integer(audit.get("exposure_gt_one"))}; 청구 4건 초과 행: {_integer(audit.get("claims_gt_four"))}. 유효한 관측은 임의로 자르지 않고 감사 수치에 남깁니다.</p>
<h3>Area 기술 통계</h3>{area_table}</section>
<section aria-labelledby="limits"><h2 id="limits">한계</h2><ul>{"".join(f"<li>{_e(item)}</li>" for item in limitations)}</ul>
<p>이 보고서는 집계 결과만 표시하며 계약별 자료나 예측값을 포함하지 않습니다. 주 데이터 유형: <strong>{_e(study.get("data_kind", "N/A"))}</strong>.</p></section>
<footer>MotorClaimLab · Python {_e(results.get("environment", {}).get("python", "N/A"))} · 실행 {_number(results.get("timing", {}).get("total_seconds"), 2)}초 · 자료 출처 일치: {_e(results.get("provenance", {}).get("source_matches_pinned", "N/A"))}</footer>
</main></body></html>"""
