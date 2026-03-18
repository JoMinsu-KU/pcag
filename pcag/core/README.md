# PCAG 공통 코어 안내

`pcag/core/`는 서비스들이 공유하는 계약, 공통 로직, 데이터 모델, 미들웨어를 담고 있다.

## 주요 하위 구성

- `contracts/`
  - Gateway, OT, Evidence, Policy, Proof Package, PLC Adapter 등 API 계약
- `database/`
  - SQLAlchemy 모델과 DB 엔진
- `middleware/`
  - API key 인증, 사람 친화형 운영 로그
- `models/`
  - 정책/검증 관련 내부 모델
- `ports/`
  - sensor / executor / simulation backend 인터페이스
- `services/`
  - `integrity_service.py`
  - `rules_validator.py`
  - `cbf_validator.py`
  - `consensus_engine.py`
  - `alternative_action.py`
- `utils/`
  - hashing, canonicalization, config loading, logging config

## 현재 코어에서 중요한 변경점

현재 구현 기준으로 아래 항목이 반영돼 있다.

- `proof_package.py` 계약 분리
- `gateway` 응답에 `alternative_actions` 포함 가능
- L1 `sensor_snapshot_hash` mismatch reject
- 운영 로그용 사람 친화 포맷 + 색상 + module/source 표시
- evidence 응답에 `created_at` 포함

## 참고

코어의 실제 의미와 현재 계약 기준은 아래 문서를 우선 본다.

- [PCAG_최종_시스템_명세서.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_최종_시스템_명세서.md)
- [PCAG_DSG_정합성_보완계획.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_DSG_정합성_보완계획.md)
