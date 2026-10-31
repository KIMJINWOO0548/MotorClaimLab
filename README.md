# MotorClaimLab

**자동차보험 청구 빈도를 분석하고 모델의 오차와 한계를 설명하는 재현 가능한 연구 프로젝트.**

보험 가입 기간이 다른 계약을 공정하게 비교하면서, 단순 평균·포아송 회귀·부스팅 모델의 예측과 집단별 과소·과대예측을 평가합니다. 채용 포트폴리오를 위한 개인 프로젝트이며 KB손해보험 또는 다른 보험사의 의뢰·검증·운영 시스템이 아닙니다.

현재 단계: **설계 완료, 구현 진행 중**. 아직 모델 성능이나 업무 효과를 주장하지 않습니다.

- 설계: [docs/DESIGN.md](docs/DESIGN.md)
- 구현 계획: [docs/superpowers/plans/2026-11-01-motorclaimlab.md](docs/superpowers/plans/2026-11-01-motorclaimlab.md)
- 데이터 출처·이용조건: [docs/DATA_SOURCE.md](docs/DATA_SOURCE.md)
- 실제 검증 상태: [docs/STATUS.md](docs/STATUS.md)

Python 3.12를 기본 실행 환경으로 사용합니다. 데이터 원본·계약별 예측·가상환경은 공개 저장소에서 제외합니다. 공개 자료는 집계 결과와 이를 재현하는 코드로 제한합니다.

## 연구 경계

자료는 과거 프랑스 자동차보험 벤치마크입니다. 현재 한국 보험시장의 성능·수익·업무 절감이나 미래 시점 일반화는 입증하지 않습니다. 예측값으로 보험료, 인수 여부 또는 보험금 지급을 결정하지 않습니다.

Original project code is licensed under MIT. Dataset and referenced documentation have separate terms; see [DATA_SOURCE](docs/DATA_SOURCE.md).
