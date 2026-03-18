# PCAG: Proof-Carrying Action Gateway

PCAG는 에이전트 또는 상위 소프트웨어가 생성한 물리 제어 명령을 바로 실행하지 않고, 증거 패키지, 무결성 검증, 다중 안전 검증, 트랜잭션형 실행 제어, 증거 장부 기록을 거쳐서만 OT 계층으로 전달하는 결정론적 안전 실행 게이트웨이이다.

## 현재 상태

기준일: 2026-03-17

현재 구현에는 아래 기능이 반영되어 있다.

- `Proof Package` 기반 요청 계약
- `L1 Integrity`에서 정책 버전, timestamp, sensor divergence, `sensor_snapshot_hash` 불일치 reject
- `Rules + CBF + Simulation` 병렬 검증과 SIL consensus
- `PREPARE -> REVERIFY -> COMMIT/ABORT` fail-closed 실행 제어
- 실행 성공 후에만 `COMMITTED` 확정
- `Evidence Ledger` 해시 체인과 non-2xx fail-hard
- PLC/Modbus 접근의 단일화(`PLC Adapter`)
- 실시간 운영 대시보드(`Dashboard`)
- live E2E 및 반복 평가 러너

## 서비스 구성

현재 서비스는 총 9개다.

| 서비스 | 포트 | 비고 |
| --- | --- | --- |
| Gateway Core | 8000 | 전체 파이프라인 오케스트레이션 |
| Safety Cluster | 8001 | `pcag-isaac` 환경에서 별도 실행 |
| Policy Store | 8002 | 활성 정책/자산 프로필 조회 |
| Sensor Gateway | 8003 | 자산 스냅샷 제공 |
| OT Interface | 8004 | PREPARE/COMMIT/ABORT |
| Evidence Ledger | 8005 | 증거 이벤트 체인 |
| Policy Admin | 8006 | 정책 등록/활성화 |
| PLC Adapter | 8007 | PLC/Modbus 단일 진입점 |
| Dashboard | 8008 | 실시간 모니터링 |

내부 서비스 URL은 `localhost` 대신 `127.0.0.1` 기준으로 맞춘다.

## 현재 기준 문서

현재 구현을 가장 정확하게 설명하는 문서는 아래 4개다.

- [PCAG_최종_시스템_명세서.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_최종_시스템_명세서.md)
- [PCAG_운영_Runbook.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_운영_Runbook.md)
- [PCAG_개발완료_구현상태_검증보고서.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_개발완료_구현상태_검증보고서.md)
- [PCAG_IJAMT_실험설계서.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_IJAMT_실험설계서.md)

과거 계획/분석 문서는 `plans/` 아래에 보존되어 있으며, 각 문서는 작성 시점의 계획 또는 분석 기록으로 취급하는 것이 맞다.

## 빠른 시작

### 1. DB 실행

```powershell
docker compose -f docker/docker-compose.db.yml up -d
```

### 2. `Safety Cluster` 실행 (`pcag-isaac`)

```powershell
conda activate pcag-isaac
python scripts/start_safety_cluster.py
```

### 3. 나머지 서비스 실행 (`pcag`)

```powershell
conda activate pcag
python scripts/start_services.py
```

### 4. 정책 시드

```powershell
python scripts/seed_policy.py
```

### 5. live E2E 실행

```powershell
python tests/e2e/run_live_gateway_eval.py
python tests/e2e/run_live_gateway_eval_repeat.py --runs 10
```

### 6. 대시보드 확인

- [http://127.0.0.1:8008/](http://127.0.0.1:8008/)

## 디렉터리 안내

- [config/README.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/config/README.md)
- [pcag/README.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/pcag/README.md)
- [scripts/README.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/scripts/README.md)
- [tests/README.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/README.md)

## 검증 메모

현재 핵심 회귀 기준은 아래 두 개다.

- mock 기반 문서정합성 검증: [README_document_conformance_eval.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/README_document_conformance_eval.md)
- 실제 서버 기반 live E2E: [README_live_gateway_eval.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/README_live_gateway_eval.md)
