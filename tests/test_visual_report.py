"""Offline presentation checks cannot substitute for a real browser audit."""

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from test_presentation import _saved

from motorclaimlab.report import render_report, write_figures


class _Outline(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.targets = []
        self.main = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.targets.append(attrs["href"][1:])
        if tag == "main":
            self.main = attrs


def test_visual_opening_contains_real_calibration_and_working_section_links():
    document = render_report(_saved())
    hero = re.search(r'<header class="study-hero".*?</header>', document, re.S)
    assert hero, "The opening must introduce the study through the actual primary chart"
    assert "Observed rate" in hero[0] and "Predicted rate" in hero[0]
    assert "청구 / 노출 연수" in hero[0]
    outline = _Outline()
    outline.feed(document)
    assert outline.main.get("id") == "report-content"
    assert "report-content" in outline.targets
    assert all(outline.ids.count(target) == 1 for target in outline.targets)
    assert len(outline.ids) == len(set(outline.ids))
    assert (
        "@media" in document and "prefers-reduced-motion" in document and "@media print" in document
    )
    assert "<script" not in document and "@import" not in document


def test_chart_series_keep_semantic_alternatives_in_high_contrast_theme(tmp_path):
    write_figures(_saved(), tmp_path)
    svg = (tmp_path / "calibration.svg").read_text(encoding="utf-8")
    assert "Observed rate" in svg and "Predicted rate" in svg
    assert "0.250" in svg and "1.500" in svg, (
        "Stored exposure-adjusted values must survive restyling"
    )
    assert "#102c3b" in svg and "#8ec7ef" in svg and "#ff956d" in svg


def test_hero_series_and_text_have_wcag_aa_contrast():
    def luminance(color):
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return sum(
            weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
        )

    background = luminance("#102c3b")
    for foreground in ("#ffffff", "#c4d4dd", "#8ec7ef", "#ff956d"):
        assert (luminance(foreground) + 0.05) / (background + 0.05) >= 4.5


def test_incomplete_calibration_notice_has_reserved_space_above_plot(tmp_path):
    result = _saved()
    del result["calibration"]["poisson_glm"][0]["observed_claims"]
    write_figures(result, tmp_path)
    root = ET.parse(tmp_path / "calibration.svg").getroot()
    texts = {node.text: node for node in root.iter() if node.tag.endswith("}text")}
    warning = texts["Incomplete calibration bins: 1"]
    legend = texts["Observed rate"]
    assert float(legend.attrib["y"]) - float(warning.attrib["y"]) > 24
