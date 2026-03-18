# PCAG 패키지 개요

`pcag/`는 PCAG 시스템의 실제 구현 코드가 들어 있는 핵심 패키지다.

## 현재 구성

- `apps/`
  - 마이크로서비스 구현
  - Gateway, Safety Cluster, Sensor Gateway, OT Interface, Policy Store, Policy Admin, Evidence Ledger, PLC Adapter, Dashboard
- `core/`
  - 계약, 데이터베이스 모델, 로깅, 공통 서비스 로직, consensus, integrity, rules, CBF 등
- `plugins/`
  - executor, sensor, simulation backend 구현

## 현재 구조의 의미

PCAG는 단순히 검증기 묶음이 아니라 아래 층을 모두 가진다.

1. 요청 계약 층
2. 무결성 검증 층
3. 병렬 안전 검증 층
4. 트랜잭션형 실행 제어 층
5. 증거 기록 층
6. 현장 I/O 중앙화 층
7. 운영 모니터링 층

즉 `pcag/` 패키지는 "검증 로직"뿐 아니라 실제 운영 가능한 안전 실행 시스템 전체를 담고 있다.

## 현재 기준 문서

- [PCAG_최종_시스템_명세서.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_최종_시스템_명세서.md)
- [PCAG_운영_Runbook.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_운영_Runbook.md)

## 관련 디렉터리

- [apps/README.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/pcag/apps/README.md)
- [core/README.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/pcag/core/README.md)
- [plugins/README.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/pcag/plugins/README.md)
