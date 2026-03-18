# PCAG 실시간 모니터링 대시보드

## 개요

이 서비스는 PCAG 전체 마이크로서비스를 실시간으로 모니터링하기 위한 운영 대시보드입니다.
단순 목업이 아니라 실제 서버, 실제 PostgreSQL, 실제 로그 파일, 실제 E2E 결과 파일을 읽어서 화면을 구성합니다.

기본 주소:

- `http://127.0.0.1:8008/`

주요 API:

- `GET /v1/health`
- `GET /v1/snapshot`
- `GET /v1/stream`

## 데이터 소스

대시보드는 아래 실제 데이터 소스를 사용합니다.

- 서비스 상태: `config/services.yaml`에 등록된 각 서비스 URL
- 정책/트랜잭션/증거: PostgreSQL
- PLC 상태: `plc_adapter /v1/health`
- 자산 스냅샷: `sensor_gateway /v1/assets/{asset_id}/snapshots/latest`
- 운영 로그: `logs/pcag.log`
- live E2E 결과:
  - `tests/e2e/results/live_gateway_eval_latest.json`
  - `tests/e2e/results/live_gateway_eval_repeat_latest.json`

## 화면 구성

- 시스템 개요
- 서비스 상태 및 지연시간 추이
- 정책/자산 요약
- 최근 트랜잭션 파이프라인
- PLC/락 상태
- Evidence 기반 최근 이벤트 흐름
- live E2E 정확도와 반복 평가 결과
- 최근 운영 로그

## 설정

대시보드 설정은 `config/services.yaml`의 `dashboard` 섹션에서 조정합니다.

- `refresh_ms`: 실시간 갱신 주기
- `window_minutes`: 분 단위 집계 창
- `max_transactions`: 최근 트랜잭션 표시 개수
- `max_assets`: 자산 카드 최대 개수
- `log_tail_lines`: 읽을 로그 줄 수

## 실행

전체 서비스를 함께 띄울 때:

```powershell
python scripts/start_services.py
```

대시보드만 단독 실행할 때:

```powershell
python -m uvicorn pcag.apps.dashboard.main:app --host 0.0.0.0 --port 8008
```

## 주의사항

- `Safety Cluster`는 기존과 동일하게 별도 환경에서 실행되어야 합니다.
- 대시보드는 실시간 요청을 보내므로, PLC/센서 응답 시간이 길면 스냅샷 생성 시간도 함께 늘어날 수 있습니다.
- 서비스 URL이 바뀌면 반드시 `config/services.yaml`을 함께 수정해야 합니다.
- 서비스 URL은 `localhost`보다 `127.0.0.1` 기준을 유지하는 편이 안정적입니다.
