"""Check the synthetic sensitivity CLI and its offline HTML in installed Chrome."""

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run(python, output):
    output.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / "synthetic.csv"
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                (
                    "IDpol",
                    "ClaimNb",
                    "Exposure",
                    "Area",
                    "VehPower",
                    "VehAge",
                    "DrivAge",
                    "BonusMalus",
                    "VehBrand",
                    "VehGas",
                    "Density",
                    "Region",
                )
            )
            for index in range(1, 301):
                writer.writerow(
                    (
                        index,
                        6 if index % 7 == 0 else index % 3,
                        1.5 if index % 4 == 0 else 0.25 * (index % 3 + 1),
                        ("A", "B", "C")[index % 3],
                        5 + index % 3,
                        index % 12,
                        25 + index % 48,
                        50 + index % 10,
                        "B1",
                        "Regular",
                        20 + index % 18,
                        "R1",
                    )
                )
        baseline = root / "baseline"
        original = source.read_bytes()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")

        def cli(*args, expected):
            process = subprocess.run(
                [str(python), "-m", "motorclaimlab", *map(str, args)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            assert process.returncode == expected, process.stderr
            return process.stdout

        cli(
            "run",
            "--input",
            source,
            "--output",
            baseline,
            "--max-iter",
            "3",
            "--bootstrap-draws",
            "5",
            expected=0,
        )
        result, selection = baseline / "results.json", baseline / "selection.json"
        originals = {path: path.read_bytes() for path in (result, selection)}
        args = (
            "sensitivity",
            "--input",
            source,
            "--results",
            result,
            "--selection",
            selection,
            "--output",
        )
        assert cli(*args, output / "comparable", expected=0).strip() == "COMPARABLE"
        assert cli(*args, root / "repeat", expected=0).strip() == "COMPARABLE"
        comparable = output / "comparable" / "artifacts"
        for name in ("sensitivity.json", "report.html", "report.md", "completion.json"):
            assert (comparable / name).read_bytes() == (
                root / "repeat" / "artifacts" / name
            ).read_bytes()
        assert source.read_bytes() == original
        source.write_bytes(original + b"\n")
        assert (
            cli(*args, output / "unavailable", expected=1).strip() == "UNAVAILABLE SOURCE_MISMATCH"
        )
        assert {path: path.read_bytes() for path in originals} == originals
        aggregate = json.loads((comparable / "sensitivity.json").read_bytes())
        claims, exposure, count, affected = 0, 0.0, 0, {}
        for index in range(1, 301):
            key = hashlib.sha256(f"20261101:split:{index}".encode("ascii")).digest()[:8]
            rank = int.from_bytes(key, "big")
            observed = 6 if index % 7 == 0 else index % 3
            years = 1.5 if index % 4 == 0 else 0.25 * (index % 3 + 1)
            if rank >= (2**64 * 80) // 100:
                claims += observed
                exposure += years
                count += 1
            if rank < (2**64 * 60) // 100:
                for name, changed in [
                    ("baseline", False),
                    ("exposure_cap", years > 1),
                    ("claim_cap", observed > 4),
                    ("both_caps", years > 1 or observed > 4),
                ]:
                    affected[name] = affected.get(name, 0) + int(changed)
        support = aggregate["evaluation"]
        assert (support["rows"], support["exposure"], support["observed_claims"]) == (
            count,
            exposure,
            claims,
        )
        assert {
            row["name"]: row["impact"]["affected_rows"] for row in aggregate["scenarios"]
        } == affected
        ranked = max(aggregate["scenarios"], key=lambda row: abs(row["test"]["deviance_delta"]))
        expected_winner = ranked["name"]
        checks = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            for state in ("comparable", "unavailable"):
                report = output / state / "artifacts" / "report.html"
                raw = report.read_text(encoding="utf-8")
                assert str(root) not in raw and "IDpol" not in raw
                for width, height in ((375, 812), (1440, 900)):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(report.resolve().as_uri())
                    assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
                    assert page.locator("header strong").inner_text() == state.upper()
                    started = perf_counter()
                    found = None
                    if state == "comparable":
                        page.keyboard.press("Tab")
                        page.keyboard.press("Enter")
                        assert page.evaluate("document.activeElement.id") == "comparison"
                        page.keyboard.press("Tab")
                        assert (
                            page.evaluate("document.activeElement.getAttribute('aria-label')")
                            == "Test results with common exposure and claims"
                        )
                        page.keyboard.press("ArrowRight")
                        rows = [
                            row.locator("th, td").all_text_contents()
                            for row in page.locator("table").first.locator("tbody tr").all()
                        ]
                        winner = max(rows, key=lambda row: abs(float(row[4])))
                        assert winner[0] == expected_winner
                        assert int(winner[2]) == affected[expected_winner]
                        expected_support = (
                            f"{count} rows · {exposure:.12g} years of exposure"
                            f" · {claims} observed claims"
                        )
                        assert expected_support in page.locator("header").inner_text()
                        found = {
                            "largest_absolute_deviance_change": winner[0],
                            "affected_train_rows": int(winner[2]),
                            "common_test_rows": count,
                            "common_test_exposure": exposure,
                            "common_observed_claims": claims,
                        }
                    else:
                        assert page.locator("table").count() == 0
                        assert "SOURCE_MISMATCH" in page.locator("header").inner_text()
                    elapsed = perf_counter() - started
                    assert elapsed < 180
                    page.screenshot(path=output / f"{state}-{width}.png", full_page=True)
                    checks.append(
                        {
                            "fixture": state,
                            "width": width,
                            "automated_keyboard_seconds": elapsed,
                            "verified": found,
                        }
                    )
                    page.close()
        (output / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
