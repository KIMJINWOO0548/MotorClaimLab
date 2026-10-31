# Status

2026-11-01 KST.

| Item | State | Evidence |
| --- | --- | --- |
| Scope, protocol, source/rights boundary | SPECIFIED | DESIGN.md, DATA_SOURCE.md |
| Public GitHub repository | created | https://github.com/KIMJINWOO0548/MotorClaimLab, main |
| Data audit and split | VERIFIED | Pinned MD5/SHA-256; 678,013 rows; 406061/136283/135669 split |
| Models and evaluation | IMPLEMENTED + synthetic VERIFIED | Three frozen models; weighted metrics and paired bootstrap |
| CLI and report | IMPLEMENTED + synthetic VERIFIED | Real temporary CSV CLI; source/overwrite boundaries; report regressions |
| Real-data model experiment | VERIFIED | Full 678,013 rows; selected poisson_hgb; test deviance 0.574883; RESULTS.md |
| Automated verification | 112 passed | Current full local suite exit 0; Ruff/format/uv dependency checks passed |
| CI | VERIFIED | Analysis 751e6f7/run 41218810116; evidence integrity dda7b54/run 41219758581; Windows 3.12 / Linux 3.12 and 3.13 success |
| Isolated wheel installation and execution | VERIFIED | Separate runtime environment; 300-row synthetic CLI outside checkout, exit 0 |
| Final online fetch CLI | VERIFIED | Fresh source directory, gzip transport and pinned checksum, exit 0 |
| Offline plot inspection | VERIFIED | Actual Matplotlib PNG model/calibration charts inspected; no browser claim |
| Published evidence integrity | VERIFIED | All ten original artifact hashes match actual Git blobs; expected hashes retained |
| Browser audit | SKIPPED / DENIED | file URL protocol rejected; no alternate surface/server workaround |

No external human review, operational use or measured business outcome is claimed.

## Renderer 2.0 supplement

The saved experiment is unchanged. New renderer-only files are in `docs/evidence/presentation-v2/`; provenance and eight derived artifacts have a separate manifest. Local full suite: **104 passed**, Ruff/format and isolated wheel rendering exit 0. Implementation `782018f` passed actual CI `41223891243` on Windows 3.12 and Linux 3.12/3.13, including original and derived Git-blob checks. [PRESENTATION_V2_VALIDATION.md](PRESENTATION_V2_VALIDATION.md) records tools, licenses, commands and limitations. Browser execution remains SKIPPED/DENIED; no workaround occurred.

## Renderer 3.0 visual supplement

The explicit user request for a bolder, distinctive UI is implemented in a chart-led petrol/coral opening and light analytical content. The local full suite now passes **108 tests**, including a reproduced missing-calibration warning/legend overlap regression and offline contrast/navigation checks. Outputs are separate in `docs/evidence/presentation-v3/`; original and v2 evidence remain unchanged. Implementation `7323b70` passed all three Windows/Linux CI jobs in actual run `41226676309`. [PRESENTATION_V3_VALIDATION.md](PRESENTATION_V3_VALIDATION.md) records packaging, publication and CI results. Actual browser layout/keyboard/responsive/print/accessibility execution remains SKIPPED/DENIED; no alternate server or browser surface was used.

## Renderer 3.1 reading-flow closure

The supplied v2 PNG/source review was compared against current v3, then only remaining support/context/exploration gaps were addressed. Exact three-model comparison remains visible; standalone interval names models/95%/fixed conditions, calibration support accompanies the curve, and native disclosures expose the 4/3/6 saved segment groups. Final local suite **112 passed**. [AUDIT_CLOSURE_V3_1.md](AUDIT_CLOSURE_V3_1.md) distinguishes resolved items, actual checks and the still unverified browser/aesthetic boundary. New outputs are in `docs/evidence/presentation-v3-1/`; all prior public evidence is preserved. No new model statistics or retraining occurred.

Implementation `6efb433791c012e273ef12a6a6fcb28dfd525b51` passed actual CI `41228214013` on Windows 3.12 and Linux 3.12/3.13. Original/current Git-blob checks passed; 31 prior public evidence files are byte-identical; isolated wheel execution outside checkout produced the same eight artifacts. Browser/page capture and aesthetic acceptance remain SKIPPED/DENIED and are assigned to the supervisor's screen-control workflow.
