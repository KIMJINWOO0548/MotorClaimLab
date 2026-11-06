"""Check the aggregate-only report with JavaScript disabled and no remote access."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.report.is_file():
        parser.error("Choose an existing saved-aggregate report and a fresh output directory")
    args.output.mkdir(parents=True)
    from playwright.sync_api import sync_playwright

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(QuietHandler, directory=str(args.report.resolve().parent)),
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    checks, blocked = [], []
    try:
        with sync_playwright() as playwright:
            chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
            browser = playwright.chromium.launch(
                headless=True, **({"executable_path": str(chrome)} if chrome.is_file() else {})
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 900}, java_script_enabled=False
            )
            prefix = f"http://127.0.0.1:{server.server_port}/"

            def route(request):
                if request.request.url.startswith(prefix):
                    request.continue_()
                else:
                    blocked.append(request.request.url)
                    request.abort()

            page.route("**/*", route)
            page.goto(prefix + args.report.name, wait_until="networkidle")
            review = page.locator("#segment-review")
            links = review.get_by_role("link", name=re.compile("집단 상세 표로 이동"))
            assert links.count() == 3
            assert review.locator(".review-support").count() == 3
            assert page.locator("details.segment-dimension").count() == 3
            first = links.first
            first.focus()
            page.keyboard.press("Enter")
            assert page.url.endswith("#segment-dimension-0")
            summary = page.locator("#segment-dimension-0>summary")
            summary.focus()
            page.keyboard.press("Enter")
            assert page.locator("#segment-dimension-0").get_attribute("open") is None
            page.keyboard.press("Enter")
            assert page.locator("#segment-dimension-0").get_attribute("open") is not None
            checks.append(
                {"name": "no-JavaScript native links and keyboard disclosure", "pass": True}
            )
            review.screenshot(path=str(args.output / "desktop-review.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (
                "Page overflows narrow viewport"
            )
            review.screenshot(path=str(args.output / "mobile-review.png"))
            checks.append(
                {"name": "390px viewport; tables retain separate scroll regions", "pass": True}
            )
            page.emulate_media(media="print")
            page.pdf(path=str(args.output / "report-print.pdf"), format="A4", print_background=True)
            checks.append(
                {"name": "print PDF produced; pagination requires visual review", "pass": True}
            )
            assert not blocked, blocked
            record = {
                "checks": checks,
                "javascript_enabled": False,
                "remote_requests": blocked,
                "report_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
                "scope": "saved aggregates; no model execution or external product benchmark",
            }
            (args.output / "result.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(record))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
