"""
Gateway Contract (Agent ↔ Gateway)
============================================
이 모듈은 외부 에이전트와 PCAG Gateway Core 간의 통신 계약을 정의합니다.

PCAG 파이프라인 위치:
  [Agent] → [100] Gateway Core

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.1
  - plans/PCAG_Modular_Architecture_Analysis.md §Gateway
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any

class ControlRequest(BaseModel):
    """
    에이전트가 PCAG에 제출하는 제어 요청.
    
    사용 경로: Agent → Gateway (POST /v1/control)
    
    에이전트는 ProofPackage(증거 패키지)를 포함한 이 요청을 통해
    OT 장비에 대한 제어 명령의 안전 검증 및 실행을 요청합니다.
    """
    transaction_id: str  # 트랜잭션 고유 ID (UUIDv4) — 전체 파이프라인(100~140)에서 요청을 추적하는 데 사용
    asset_id: str        # 대상 자산(장비) ID — Policy Store에서 정책 조회 및 OT Interface 라우팅에 사용
    proof_package: dict  # 증거 패키지 (ProofPackage JSON) — 실행할 액션 시퀀스와 안전성 증거(CoT, RAG 등)를 포함

class ControlResponse(BaseModel):
    """
    PCAG가 에이전트에게 반환하는 제어 처리 결과.
    
    사용 경로: Gateway → Agent (응답)
    
    요청된 제어 명령의 최종 상태(성공, 거부, 실패)와 그 이유를 포함합니다.
    """
    transaction_id: str  # 요청 시 받은 트랜잭션 ID 반환
    status: Literal["COMMITTED", "REJECTED", "UNSAFE", "ABORTED", "ERROR"]  # 최종 처리 상태
    # COMMITTED: OT 장비에 명령 전달 완료
    # REJECTED: 무결성 검증 실패 또는 정책 위반
    # UNSAFE: 안전 검증(Safety Cluster) 실패
    # ABORTED: 2PC 과정 중 타임아웃 또는 기타 오류로 중단
    # ERROR: 시스템 내부 오류 (Fail-Hard)
    
    reason: Optional[str] = None  # 사람이 읽을 수 있는 결과 사유 (예: "Rule 3 violation")
    reason_code: Optional[str] = None  # 기계가 읽을 수 있는 상세 코드 (예: "RULE_VIOLATION")
    evidence_ref: Optional[str] = None  # Evidence Ledger에 기록된 트랜잭션 증거의 참조 ID (해시 등)
    alternative_action: Optional[dict] = None  # (선택적) 안전 검증 실패 시, 시스템이 제안하는 안전한 대안 액션
