# Status

2026-11-01 KST.

| Item | State | Evidence |
| --- | --- | --- |
| Scope, protocol, source/rights boundary | SPECIFIED | DESIGN.md, DATA_SOURCE.md |
| Public GitHub repository | created | https://github.com/KIMJINWOO0548/MotorClaimLab, main |
| Data audit and split | VERIFIED | Pinned MD5/SHA-256; 678,013 rows; 406061/136283/135669 split |
| Models and evaluation | IMPLEMENTED + synthetic VERIFIED | Three frozen models; weighted metrics and paired bootstrap |
| CLI and report | IMPLEMENTED + synthetic VERIFIED | Real temporary CSV CLI; source/overwrite boundaries; report regressions |
| Real-data model experiment | pending | Source audit is not model-performance evidence |
| Automated verification | 88 passed | Full local suite exit 0; Ruff/format/dependency checks passed |
| CI | configured, not yet run | A workflow is not a CI run |
| Browser audit | SKIPPED / DENIED | file URL protocol rejected; no alternate surface/server workaround |

No external human review, operational use or measured business outcome is claimed.
