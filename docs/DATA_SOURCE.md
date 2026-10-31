# Data source and rights boundary

Checked 2026-11-01 KST against primary sources.

| Field | Source metadata |
| --- | --- |
| Dataset | freMTPL2freq, OpenML data ID 41214, version 1 |
| Format | ARFF |
| OpenML license field | `CC0` |
| Download | https://openml.org/data/v1/download/20649148/freMTPL2freq.arff |
| Published MD5 | `f8875568bf0ca622929105197e2db613` |
| Metadata | https://www.openml.org/api/v1/json/data/41214 |

CC0 is OpenML's asserted dataset license. The original insurer's permission and collection provenance have not been independently authenticated. The CASdatasets maintainer identifies the source as **Unknown private insurer**, approximately 2011–2013, mostly one year per policy. Its R package GPL license is separate and does not establish original data rights. This repository redistributes no raw observations or fitted models.

References:

- Maintainer: https://dutangc.github.io/CASdatasets/reference/freMTPL.html
- Source documentation: https://raw.githubusercontent.com/dutangc/CASdatasets/master/man/freMTPL.Rd
- Package terms: https://raw.githubusercontent.com/dutangc/CASdatasets/master/DESCRIPTION
- Official model example: https://scikit-learn.org/stable/auto_examples/linear_model/plot_poisson_regression_non_normal_loss.html
- Leakage guidance: https://scikit-learn.org/stable/common_pitfalls.html#data-leakage

Descriptions disagree on row count (677,991 versus 678,013); every actual run records the downloaded dimensions and SHA-256 rather than copying the description. MD5 checks download identity only; SHA-256 fingerprints the bytes and neither authenticates authorship or rights.

Fields: IDpol, ClaimNb, Exposure, Area, VehPower, VehAge, DrivAge, BonusMalus, VehBrand, VehGas, Density, Region. IDpol is a policy identifier; ClaimNb is the count target; Exposure is the observed duration in years. There is no reliable observation-date column. No chronological validity is claimed.

Unusual positive exposures above one year and high claim counts are retained and counted in the audit. Clipping used by other tutorials is not an authenticated source correction. Nonfinite/zero/negative exposure, invalid count targets, empty categories and duplicate policy identifiers are rejected explicitly.
