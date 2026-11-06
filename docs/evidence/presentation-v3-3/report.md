# MotorClaimLab · frozen-result comparison

과거 프랑스 자료에 대한 공개 데이터 실험입니다.

- Selected model: poisson_hgb (selected on validation)
- Rows: 678,013; data kind: openml_pinned; seed: 20261101
- Study exposure: 358,499.45 years (saved train/validation/test population).
- Full-input audit: 678,013 rows; exposure 358,499.45 years.
- Renderer 3.3; source values are saved aggregates; no model execution.

## Validation and test comparison

| Model | Validation deviance | Test deviance | Test weighted MAE | Observed claims | Predicted claims | Ratio |
|---|---:|---:|---:|---:|---:|---:|
| Training mean | 0.627851 | 0.626294 | 0.188820 | 7,220.00 | 7,204.52 | 1.0021 |
| Poisson GLM | 0.606750 | 0.605803 | 0.186772 | 7,220.00 | 7,203.08 | 1.0023 |
| Poisson HGB · 검증 분할에서 선택 | 0.575899 | 0.574883 | 0.182861 | 7,220.00 | 7,176.99 | 1.0060 |

## Paired uncertainty

Poisson HGB − Training mean: **-0.05141**; 95% paired interval **[-0.05512, -0.04785]**.
반복 200; seed 20261101.
0은 차이 없음이며 음수는 선택 모델에 유리합니다. 구간은 고정 분할과 frozen fits에 조건부이며 재학습·미래 시점 불확실성을 포함하지 않습니다.

<details id="provenance"><summary>데이터·코드·seed·split 출처</summary><p>아래 코드 해시는 동결 실험의 분석 코드입니다. 현재 표현 renderer의 해시는 별도 presentation manifest에 기록합니다.</p><pre>{
  &quot;data&quot;: {
    &quot;source_matches_pinned&quot;: true,
    &quot;source_md5&quot;: &quot;f8875568bf0ca622929105197e2db613&quot;,
    &quot;source_sha256&quot;: &quot;a45363e056e2ea56408b38eeb9d4d04d7f6c6982eb7a14ed5e807c7c71807cdd&quot;
  },
  &quot;environment&quot;: {
    &quot;packages&quot;: {
      &quot;matplotlib&quot;: &quot;3.11.2&quot;,
      &quot;numpy&quot;: &quot;2.5.4&quot;,
      &quot;pandas&quot;: &quot;2.3.3&quot;,
      &quot;scikit-learn&quot;: &quot;1.9.1&quot;,
      &quot;scipy&quot;: &quot;1.18.1&quot;,
      &quot;threadpoolctl&quot;: &quot;3.7.0&quot;
    },
    &quot;platform&quot;: &quot;Windows&quot;,
    &quot;python&quot;: &quot;3.12.10&quot;
  },
  &quot;original_experiment&quot;: {
    &quot;code_sha256&quot;: &quot;d825b99db2e819d31df1e19dc6915d1cb1f95a1c4c8503de8ec36907da7d4e7d&quot;,
    &quot;git_commit&quot;: &quot;751e6f760489ead0f88f63cd68fb52abe19b4d4d&quot;
  },
  &quot;seed&quot;: 20261101,
  &quot;selection_split&quot;: &quot;validation&quot;,
  &quot;settings&quot;: {
    &quot;bootstrap_draws&quot;: 200,
    &quot;glm&quot;: {
      &quot;alpha&quot;: 0.0001,
      &quot;max_iter&quot;: 300,
      &quot;tol&quot;: 1e-06
    },
    &quot;hgb&quot;: {
      &quot;early_stopping&quot;: false,
      &quot;learning_rate&quot;: 0.05,
      &quot;loss&quot;: &quot;poisson&quot;,
      &quot;max_iter&quot;: 100,
      &quot;max_leaf_nodes&quot;: 15,
      &quot;min_samples_leaf&quot;: 100
    },
    &quot;max_iter&quot;: 100,
    &quot;max_rows&quot;: null,
    &quot;seed&quot;: 20261101,
    &quot;split_method&quot;: &quot;sha256-policy-id-60-20-20&quot;,
    &quot;test_used_for_selection&quot;: false,
    &quot;thread_limit&quot;: 2
  },
  &quot;splits&quot;: {
    &quot;test&quot;: {
      &quot;claims&quot;: 7220,
      &quot;exposure&quot;: 71734.83429298601,
      &quot;membership_sha256&quot;: &quot;d34de04bdf559c4fbab13745a7bc59c6f693c9dadb27c94f0f3891e3a3c4be0d&quot;,
      &quot;rows&quot;: 135669
    },
    &quot;train&quot;: {
      &quot;claims&quot;: 21577,
      &quot;exposure&quot;: 214840.51823115503,
      &quot;membership_sha256&quot;: &quot;2295601535e14bfdf16d124977749d35ccab93f8052860b012e594dd555bc025&quot;,
      &quot;rows&quot;: 406061
    },
    &quot;validation&quot;: {
      &quot;claims&quot;: 7305,
      &quot;exposure&quot;: 71924.09293884273,
      &quot;membership_sha256&quot;: &quot;f2dcbad889e638c0c614deec5443961be39ba9ecbe1f38306018fc6c380e6b46&quot;,
      &quot;rows&quot;: 136283
    }
  }
}</pre></details>

## Selected-model segments

청구 건수의 기술적 차이: 관측 − 예측이 양수면 과소예측, 음수면 과대예측입니다. 인과 설명·보험금 판단·유의성 판정이 아닙니다.

| Segment / group | Rows | Exposure | Poisson deviance | Observed / predicted | Observed − predicted (claims) |
|---|---:|---:|---:|---:|---|
| DrivAge: &lt;25 | 5,991 | 2,488.88 | 0.9870 | 1.1123 | 과소예측 · +50.19 |
| DrivAge: 25-39 | 45,697 | 21,678.85 | 0.5491 | 0.9372 | 과대예측 · -130.88 |
| DrivAge: 40-59 | 61,562 | 33,504.94 | 0.5821 | 1.0385 | 과소예측 · +127.30 |
| DrivAge: 60+ | 22,419 | 14,062.17 | 0.5245 | 0.9973 | 과대예측 · -3.60 |
| VehAge: &lt;5 | 56,453 | 25,896.70 | 0.6795 | 1.0115 | 과소예측 · +35.37 |
| VehAge: 5-9 | 34,467 | 20,030.69 | 0.5563 | 1.0322 | 과소예측 · +62.20 |
| VehAge: 10+ | 44,749 | 25,807.44 | 0.4843 | 0.9749 | 과대예측 · -54.56 |
| Area: A | 20,760 | 12,332.80 | 0.4965 | 1.0235 | 과소예측 · +23.76 |
| Area: B | 14,917 | 8,463.41 | 0.5125 | 1.0077 | 과소예측 · +5.77 |
| Area: C | 38,656 | 21,063.28 | 0.5556 | 1.0371 | 과소예측 · +73.64 |
| Area: D | 30,246 | 15,432.26 | 0.5846 | 0.9200 | 과대예측 · -135.67 |
| Area: E | 27,541 | 12,828.36 | 0.6897 | 1.0461 | 과소예측 · +69.49 |
| Area: F | 3,549 | 1,614.72 | 0.7473 | 1.0272 | 과소예측 · +6.03 |

Sparse: rows < 50 or exposure < 10 years. Metrics are observations, not an approval/compliance status.

## Limitations

- 빈도는 청구 건수 / 관측 노출 연수이며 적합·평가에 노출 가중치를 사용합니다.
- 시간 순서 검증, 현재 국내 보험 적용성 및 업무 효과는 입증하지 않았습니다.
- 내부 AI 보조 검토는 외부 인간·보험계리 전문가 검수가 아닙니다.
- No observation-date field: policy holdout is not a temporal validation.
- OpenML asserts CC0; original-insurer permission/provenance is not independently verified.
- No clipping of unusual valid exposures/counts; source anomalies may affect the comparison.
- Model selected on validation; test segments are exploratory, not threshold optimization.
- Bootstrap interval is conditional on this split and frozen fits; not retraining uncertainty.
- No causal, fairness, pricing, underwriting, claim-decision or measured business-impact claim.
- Internal AI-assisted review is not external human or actuarial review.
- Historical French benchmark; current Korean or KB insurance validity is untested.
