from pathlib import Path

from motorclaimlab.report import render_markdown, render_report, write_figures


def _results():
    metric = {
        "rows": 2,
        "exposure": 3.0,
        "mean_poisson_deviance": 0.2,
        "weighted_mae": 0.1,
        "observed_claims": 2.0,
        "predicted_claims": 1.5,
        "observed_predicted_ratio": 1.333333,
    }
    return {
        "selected_model": "poisson_glm <script>alert(1)</script>",
        "study": {
            "name": "MotorClaimLab",
            "seed": 20261101,
            "sampled": False,
            "rows": 678013,
            "selection_split": "validation",
            "data_kind": "local_unverified <tag>",
        },
        "audit": {
            "rows": 678013,
            "claims": 1000,
            "exposure": 900000.0,
            "exposure_gt_one": 2,
            "claims_gt_four": 1,
        },
        "splits": {
            name: {"rows": 2, "claims": 2, "exposure": 3.0, "membership_sha256": "a" * 64}
            for name in ("train", "validation", "test")
        },
        "metrics": {
            split: {
                name: dict(metric, mean_poisson_deviance=score)
                for name, score in (("mean", 0.4), ("poisson_glm", 0.2), ("poisson_hgb", 0.3))
            }
            for split, score in (("validation", 0.2), ("test", 0.25))
        },
        "calibration": {
            "poisson_glm <script>alert(1)</script>": [
                dict(
                    metric, **{"bin": 1, "observed_claims": 1, "predicted_claims": 2, "exposure": 4}
                ),
                dict(
                    metric, **{"bin": 2, "observed_claims": 3, "predicted_claims": 1, "exposure": 2}
                ),
            ]
        },
        "segments": [
            {
                "segment": "Area",
                "group": "Z <img src=x>",
                "rows": 2,
                "exposure": 3.0,
                "observed_claims": 2.0,
                "predicted_claims": 1.5,
                "mean_poisson_deviance": 0.2,
                "weighted_mae": 0.1,
                "observed_predicted_ratio": None,
                "sparse": True,
            }
        ],
        "bootstrap": {
            "selected_minus_baseline": -0.1,
            "ci_lower": -0.2,
            "ci_upper": 0.01,
            "draws": 200,
            "seed": 20261101,
        },
        "eda": {
            "overall": {"Area": "North <script>"},
            "by_area": [{"Area": "North <script>", "rows": 2, "exposure": 3.0, "claims": 2.0}],
        },
        "timing": {"total_seconds": 10.2, "fit_seconds": 4.5},
        "environment": {"python": "3.11.2", "packages": {"matplotlib": "3.11.2"}},
        "provenance": {
            "source_sha256": "b" * 64,
            "source_md5": "c" * 32,
            "source_matches_pinned": False,
            "code_sha256": "d" * 64,
            "git_commit": "e" * 40,
        },
        "limitations": ["Synthetic fixture <unsafe>"],
    }


def test_html_is_standalone_escaped_and_shows_selected_model_and_aggregates():
    html = render_report(_results())
    assert "poisson_glm &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Z &lt;img src=x&gt;" in html
    assert "678,013" in html
    assert "1.3333" in html
    assert "validação" not in html
    assert "Validation" in html and "Test results" in html
    assert "Test-set Poisson deviance" in html and "Calibration by prediction bin" in html
    assert "<script" not in html and "<img" not in html
    assert 'href="http' not in html and 'src="http' not in html
    assert "data:image/svg+xml" not in html
    assert html.count("<svg") >= 2


def test_markdown_reports_selection_test_and_null_ratio():
    markdown = render_markdown(_results())
    assert "poisson_glm &lt;script&gt;alert(1)&lt;/script&gt;" in markdown
    assert "validation" in markdown.lower() and "test" in markdown.lower()
    assert "N/A" in markdown
    assert "Synthetic fixture &lt;unsafe&gt;" in markdown


def test_write_figures_creates_actual_standalone_svg_files(tmp_path: Path):
    paths = write_figures(_results(), tmp_path)
    assert [path.name for path in paths] == ["model-comparison.svg", "calibration.svg"]
    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert path.is_file() and content.startswith("<?xml")
        assert "<svg" in content and 'href="http' not in content
    calibration = paths[1].read_text(encoding="utf-8")
    assert "0.250" in calibration


def test_calibration_bins_keep_numeric_rank_order(tmp_path):
    import xml.etree.ElementTree as ET

    result = _results()
    selected = result["selected_model"]
    base = result["calibration"][selected][0]
    result["calibration"][selected] = [dict(base, bin=number) for number in range(1, 11)]
    paths = write_figures(result, tmp_path)
    root = ET.parse(paths[1]).getroot()
    ns = {"s": "http://www.w3.org/2000/svg"}
    tick_groups = [
        element
        for element in root.findall(".//s:g", ns)
        if element.get("id", "").startswith("xtick_")
    ]
    labels = [group.find(".//s:text", ns).text for group in tick_groups]
    assert labels == [str(number) for number in range(1, 11)]


def test_sql_area_schema_labels_are_rendered():
    result = _results()
    result["eda"]["by_area"] = [
        {"area": "ACTUAL_AREA_LABEL", "rows": 10, "claims": 3, "exposure": 8.0, "frequency": 0.375}
    ]
    assert "ACTUAL_AREA_LABEL" in render_report(result)


def test_chart_exports_include_real_png_for_offline_visual_review(tmp_path):
    write_figures(_results(), tmp_path)
    for name in ["model-comparison.png", "calibration.png"]:
        assert (tmp_path / name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_eda_table_is_included_once():
    assert render_report(_results()).count("Descriptive Area aggregates") == 1


def test_sparse_segments_are_flagged_per_row_in_html_and_markdown():
    result = _results()
    base = result["segments"][0]
    result["segments"] = [dict(base, group=f"SPARSE_CASE_{number}") for number in range(4)]
    document = render_report(result)
    markdown = render_markdown(result)
    for number in range(4):
        row = next(part for part in document.split("</tr>") if f"SPARSE_CASE_{number}" in part)
        assert "Sparse" in row
        line = next(line for line in markdown.splitlines() if f"SPARSE_CASE_{number}" in line)
        assert "Sparse" in line


def test_unverified_local_input_is_not_presented_as_verified_french_public_data():
    result = _results()
    result["study"]["data_kind"] = "local_unverified"
    document = render_report(result)
    markdown = render_markdown(result)
    assert "로컬 입력" in document and "로컬 입력" in markdown
    assert "과거 프랑스 자료에 대한 공개 데이터 실험입니다" not in document
    assert "프랑스 자동차보험 자료를 이용한 교육용 빈도 비교입니다" not in markdown
