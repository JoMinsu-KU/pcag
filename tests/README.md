# PCAG 테스트 안내

`tests/`는 unit, integration, live/mock E2E, 외부 환경 연동 테스트를 포함하는 검증 디렉터리다.

## 테스트 층

### Unit

`tests/unit/`

현재 핵심 범위:

- consensus
- CBF
- rules
- integrity
- evidence ledger
- OT interface
- PLC adapter
- Safety Cluster 병렬화
- logging
- contracts

### Integration

`tests/integration/`

현재 핵심 범위:

- Gateway 파이프라인 mock 통합
- PostgreSQL 연동

### E2E

`tests/e2e/`

현재 기준으로 가장 중요한 두 개는 아래다.

1. 문서정합성 mock E2E
- [README_document_conformance_eval.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/README_document_conformance_eval.md)

2. 실제 서버 기반 live E2E
- [README_live_gateway_eval.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/README_live_gateway_eval.md)

legacy 시나리오 파일(`test_three_scenarios.py`, `test_all_scenarios.py`, `test_real_pipeline.py` 등)은 남아 있지만, 현재 상태 검증의 우선 기준은 dataset 기반 runner들이다.

## 권장 실행

```powershell
pytest tests/unit/
pytest tests/integration/
python tests/e2e/run_document_conformance_eval.py
python tests/e2e/run_live_gateway_eval.py
python tests/e2e/run_live_gateway_eval_repeat.py --runs 10
```

## 결과물

- live 단일 실행 결과:
  - [live_gateway_eval_latest.json](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/results/live_gateway_eval_latest.json)
- live 반복 실행 결과:
  - [live_gateway_eval_repeat_latest.json](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/results/live_gateway_eval_repeat_latest.json)

## 참고 문서

- [PCAG_Test_Documentation.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/archive/PCAG_Test_Documentation.md)
- [PCAG_문서_현행상태_색인.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_문서_현행상태_색인.md)
