# Visual presentation 3.0

The user requested a distinctive, contemporary, more expressive portfolio UI after finding renderer 2.0 too restrained. This changes the presentation, not the experiment. The original ten evidence files, their expected hashes, and presentation-v2 remain byte-identical.

## Direction

The opening pairs oversized Korean study typography with the actual saved calibration curve. It borrows the clarity and pace of automotive instrumentation rather than filling a generic dashboard with decorative metrics. A small custom lane-shaped wordmark and a single coral navigation action provide identity. The source context is visible before scrolling.

The dark opening transitions into light analytical content. Comparison and uncertainty use a split layout; the full three-model numeric table follows. Calibration totals, sparse segment rows and full provenance remain available. No chart is a fictional timeline or live feed.

| Token | Value / use |
| --- | --- |
| Petrol | `#102c3b`, opening and primary ink |
| Paper | `#f2f5f7`, quiet report background |
| White | `#ffffff`, analytical surface and hero title |
| Sky | `#8ec7ef`, observed rate on dark background |
| Coral | `#ff956d`, predicted rate and primary navigation action |
| Cobalt | `#315bdf`, selected model on light background |
| Type | Local Bahnschrift for Latin display, local Korean sans fallback, system sans for reading; no remote font request |

The initial sketch was a large score with several supporting tiles. That repeated a generic portfolio pattern and was rejected before implementation. The actual exposure-adjusted curve now carries the first-screen visual interest. No KPI-card grid, radar, cloud service, JS framework, extra dependency or copied reference asset is needed.

## Scope and acceptance

Changes reach report.py (HTML/CSS and existing Matplotlib chart styles), renderer version, related tests, current presentation hash guard, new presentation-v3 outputs and docs. Existing experiment/model/evaluation/data code is outside scope. render_report callers and CLI keep their interfaces. Escaping, local/unverified wording, missing-data handling, fixed-fit uncertainty, explicit source metadata and no-overwrite behavior remain.

Native section anchors, a skip link, visible keyboard focus, horizontal table scrolling, responsive reflow, print styles and reduced-motion handling are encoded in HTML/CSS. These are offline structural checks, not verified browser interactions. The existing file-URL security denial remains; no alternate server/surface is permitted.

The current Git-blob guard advances to presentation-v3. Historical presentation-v2 sources are traceable at commit 782018fa96cdd94649d72da4a0b9c48bfd910151; its original manifest is preserved rather than rewritten to identify new renderer source. The new manifest binds original input hashes to renderer 3.0 sources and eight new derived outputs. No refitting or reevaluation occurs.

Validation: observe independent presentation RED, run affected/full tests, inspect actual generated PNGs, verify offline HTML/SVG structure and contrast, build/install/run wheel outside checkout, preserve original and v2 bytes, forward commit/push and check actual CI. Visual browser layout/accessibility remains unverified due to the existing denial.
