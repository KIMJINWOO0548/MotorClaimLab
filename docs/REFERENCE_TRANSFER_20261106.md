# 집단별 청구 차이 읽기 개선

기존 집단 표는 관측·예측 청구와 비율을 제공하지만 방향을 사람이 계산해야 했다. renderer 3.3은 같은 저장 집계에서 `관측 − 예측` 청구 건수와 과소/과대예측 방향을 HTML·Markdown에 함께 표시한다. 빈 값·불리언·문자열·음수·무한/NaN 입력은 `판정 불가 · N/A`다. 색상 없이도 방향을 읽을 수 있으며 기존 Sparse·행 수·노출량을 보존한다. 반올림 전 부호를 사용한다.

[Replica 조사 기록](../replica/recon.md)과 REA 실행 요약에서 출처·직접 관찰·독자 설계를 구분한다. 기존 실험, 모델 선택, 분할·seed, 원본과 41개 기존 공개 증거는 재생성하지 않았다. renderer 버전은 3.2에서 3.3으로 올렸고 두 기존 manifest 버전 검사의 기대값만 새 명세에 맞게 올렸다.

## 실제 검증

Windows / Python 3.12, 기존 desktop 가상환경을 읽기 전용으로 재사용했다. `PYTHONPATH`는 이 checkout의 `src`다. 새 패키지는 설치하지 않았다.

| 검사 | 실제 결과 |
|---|---|
| 수정 전 전체 `pytest -q` | 기본 임시 디렉터리 초기화 OSError로 102 통과·41 setup 오류, exit 1 |
| 수정 전 `pytest --ignore=tests/test_prediction_direction.py --basetemp=reports/runs/reference-20261106/baseline-temp --tb=short -q` | 143 통과, exit 0 |
| 새 `tests/test_prediction_direction.py` 구현 전 | 독립 9개 실패, exit 1 |
| 새 테스트 구현 후 | 9 통과, exit 0 |
| 전체 `pytest --basetemp=reports/runs/reference-20261106/final-temp --tb=short -q` | 152 통과, exit 0 |
| `python -m ruff check src tests scripts` | 통과, exit 0 |
| `python -m ruff format --check src tests scripts` | 26개 파일 형식 일치, exit 0 |
| `python scripts/check_evidence.py` | 기존 10개 Git blob 증거 일치, exit 0 |
| `python scripts/check_presentation.py --renderer-ref 6efb433791c012e273ef12a6a6fcb28dfd525b51` | 역사적 v3.1 입력2·renderer2·산출물8 일치, exit 0 |
| `python <Replica>/replica-diff/parity.py replica/features.csv --json` | 선정된 기존 패턴 1개 확인·독자 추가2개·범위 밖1개, exit 0 |
| `python -m motorclaimlab render --results docs/evidence/benchmark/results.json --selection docs/evidence/benchmark/selection.json --output docs/evidence/presentation-v3-3` | 기존 집계에서 별도 새 보고서·그림8개·manifest 생성, exit 0; 모델 실행 false |
| `python reports/runs/reference-20261106/verify_render.py` | 새 manifest의 입력2·renderer source2·산출물8 해시 및 새 열 확인, exit 0 |

전체 실행 원문은 Git에서 제외된 `reports/runs/reference-20261106/`에 있다. `check_presentation.py --renderer-commit ...`는 옵션 이름 오류로 실패했으며 올바른 `--renderer-ref`로 정정했다. 원래 v3.1 산출물은 역사적 renderer 커밋으로 검증한다. 브라우저·키보드·실제 화면·모바일·인쇄 검사는 기존 접근 거절 경계 때문에 실행하지 않았다. 새 데이터 다운로드·실험 재학습·실계약 예측·배포·외부 인간/계리 검수는 수행하지 않았다. 커밋·push·원격 CI는 상위 작업의 최종 기록으로 확인한다.
