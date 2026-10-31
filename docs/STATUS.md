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
| Automated verification | 88 passed | Full local suite exit 0; Ruff/format/dependency checks passed |
| CI | VERIFIED | 751e6f7, run 41218810116: Windows 3.12 / Linux 3.12 and 3.13, all three jobs success |
| Isolated wheel installation and execution | VERIFIED | Separate runtime environment; 300-row synthetic CLI outside checkout, exit 0 |
| Final online fetch CLI | VERIFIED | Fresh source directory, gzip transport and pinned checksum, exit 0 |
| Offline plot inspection | VERIFIED | Actual Matplotlib PNG model/calibration charts inspected; no browser claim |
| Browser audit | SKIPPED / DENIED | file URL protocol rejected; no alternate surface/server workaround |

No external human review, operational use or measured business outcome is claimed.
