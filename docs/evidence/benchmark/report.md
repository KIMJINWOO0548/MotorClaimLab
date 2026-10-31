# MotorClaimLab frequency study

과거 프랑스 자료에 대한 공개 데이터 실험입니다. 현재 한국 시장의 성능이나 보험 업무 효과를 입증하지 않았습니다.

- Selected model: poisson_hgb (selected on validation)
- Data kind: openml_pinned; rows: 678,013; sampled: False

## Test results

| Model | Rows | Exposure | Poisson deviance | Weighted MAE | Observed claims | Predicted claims | Ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| Training mean | 135,669 | 71,734.83 | 0.6263 | 0.1888 | 7,220.00 | 7,204.52 | 1.0021 |
| Poisson GLM | 135,669 | 71,734.83 | 0.6058 | 0.1868 | 7,220.00 | 7,203.08 | 1.0023 |
| Poisson HGB | 135,669 | 71,734.83 | 0.5749 | 0.1829 | 7,220.00 | 7,176.99 | 1.0060 |

## Validation results

| Model | Poisson deviance |
|---|---:|
| Training mean | 0.6279 |
| Poisson GLM | 0.6068 |
| Poisson HGB | 0.5759 |

## Selected-model segments

| Segment / group | Rows | Exposure | Poisson deviance | Observed / predicted |
|---|---:|---:|---:|---:|
| DrivAge: &lt;25 | 5,991 | 2,488.88 | 0.9870 | 1.1123 |
| DrivAge: 25-39 | 45,697 | 21,678.85 | 0.5491 | 0.9372 |
| DrivAge: 40-59 | 61,562 | 33,504.94 | 0.5821 | 1.0385 |
| DrivAge: 60+ | 22,419 | 14,062.17 | 0.5245 | 0.9973 |
| VehAge: &lt;5 | 56,453 | 25,896.70 | 0.6795 | 1.0115 |
| VehAge: 5-9 | 34,467 | 20,030.69 | 0.5563 | 1.0322 |
| VehAge: 10+ | 44,749 | 25,807.44 | 0.4843 | 0.9749 |
| Area: A | 20,760 | 12,332.80 | 0.4965 | 1.0235 |
| Area: B | 14,917 | 8,463.41 | 0.5125 | 1.0077 |
| Area: C | 38,656 | 21,063.28 | 0.5556 | 1.0371 |
| Area: D | 30,246 | 15,432.26 | 0.5846 | 0.9200 |
| Area: E | 27,541 | 12,828.36 | 0.6897 | 1.0461 |
| Area: F | 3,549 | 1,614.72 | 0.7473 | 1.0272 |

## Limitations

- 빈도는 청구 건수를 관측 노출 연수로 나눈 값이며 성과 지표는 노출 가중치를 사용합니다.
- 차이는 고정된 적합 모델과 분할을 조건으로 한 쌍체 부트스트랩이며 재학습 불확실성을 나타내지 않습니다.
- 자료에 신뢰할 만한 날짜가 없어 시간 순서 검증과 현재 한국 적용성을 주장하지 않습니다.
- 내부 AI 보조 검토는 독립된 보험계리사 또는 전문가 검토가 아닙니다.
- No observation-date field: policy holdout is not a temporal validation.
- OpenML asserts CC0; original-insurer permission/provenance is not independently verified.
- No clipping of unusual valid exposures/counts; source anomalies may affect the comparison.
- Model selected on validation; test segments are exploratory, not threshold optimization.
- Bootstrap interval is conditional on this split and frozen fits; not retraining uncertainty.
- No causal, fairness, pricing, underwriting, claim-decision or measured business-impact claim.
- Internal AI-assisted review is not external human or actuarial review.
- Historical French benchmark; current Korean or KB insurance validity is untested.
