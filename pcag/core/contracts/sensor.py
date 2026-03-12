"""
Sensor Contract (Gateway ↔ Sensor Gateway)
============================================
이 모듈은 Gateway Core와 Sensor Gateway 간의 통신 계약을 정의합니다.

PCAG 파이프라인 위치:
  [Sensor Gateway] → [100] Gateway Core

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.4
  - plans/PCAG_Modular_Architecture_Analysis.md §SensorGateway
"""

from pydantic import BaseModel, Field
from typing import Optional

class SensorSnapshotResponse(BaseModel):
    """
    최신 센서 스냅샷을 반환하는 응답 구조.
    
    사용 경로: Gateway Core → Sensor Gateway (GET /v1/assets/{asset_id}/snapshots/latest)
    
    특정 자산(Asset)의 현재 센서 상태와 데이터 무결성 검증을 위한 해시 및 신뢰성 지수를 포함합니다.
    """
    asset_id: str  # 센서 데이터가 속한 대상 자산 ID
    snapshot_id: str  # 스냅샷 고유 ID (생성 시점의 UUID 또는 타임스탬프 기반)
    timestamp_ms: int  # 데이터 수집 시각 (Unix Timestamp ms) — 데이터의 최신성을 보장하기 위해 사용
    sensor_snapshot: dict  # 실제 센서 데이터 페이로드 (키-값 쌍, 예: {"temperature": 36.5, "pressure": 1013})
    
    sensor_snapshot_hash: str = Field(pattern=r'^[a-fA-F0-9]{64}$')
    # 센서 데이터의 SHA-256 해시 — 데이터 전송 중 위변조 여부를 검증하기 위해 사용 (Integrity Service)
    
    sensor_reliability_index: float = Field(ge=0.0, le=1.0)
    # 센서 데이터 신뢰성 지수 (0.0 ~ 1.0) — 센서 오작동, 노이즈, 통신 불량 등을 고려한 데이터 품질 지표
