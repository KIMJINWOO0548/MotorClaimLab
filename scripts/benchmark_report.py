"""Measure saved-aggregate HTML/Markdown rendering in fresh local processes.

No download, fitting, model import, or policy-level input is required. Peak RSS
includes Python/Matplotlib imports; wall time covers the two render calls only.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


def peak_rss_bytes() -> int:
    if sys.platform == "win32":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "PeakWorkingSetSize",
                    "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def worker(source: Path) -> dict:
    import motorclaimlab.report as report
    from motorclaimlab.report import RENDERER_VERSION, render_markdown, render_report

    content = source.read_bytes()
    results = json.loads(content)
    start = time.perf_counter()
    document = render_report(results).encode("utf-8")
    markdown = render_markdown(results).encode("utf-8")
    elapsed = time.perf_counter() - start
    return {
        "renderer_version": RENDERER_VERSION,
        "renderer_source_sha256": hashlib.sha256(Path(report.__file__).read_bytes()).hexdigest(),
        "input_sha256": hashlib.sha256(content).hexdigest(),
        "render_seconds": elapsed,
        "peak_rss_bytes": peak_rss_bytes(),
        "html_bytes": len(document),
        "markdown_bytes": len(markdown),
        "html_sha256": hashlib.sha256(document).hexdigest(),
        "markdown_sha256": hashlib.sha256(markdown).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.results), allow_nan=False))
        return
    if args.output is None or args.output.exists() or args.repeats < 1:
        parser.error("Choose a fresh --output file and at least one repetition")
    records = []
    for _ in range(args.repeats):
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--results",
                str(args.results.resolve()),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        records.append(json.loads(completed.stdout))
    result = {
        "scope": "same saved aggregates, HTML+Markdown render only; fresh process per repetition",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "model_execution": False,
        "median_render_seconds": statistics.median(row["render_seconds"] for row in records),
        "median_peak_rss_bytes": statistics.median(row["peak_rss_bytes"] for row in records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}))


if __name__ == "__main__":
    main()
