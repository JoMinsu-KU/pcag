"""
공통 계약 (Common Contracts)
============================================
이 모듈은 PCAG 시스템의 여러 서비스 간에 공유되는 공통 데이터 모델 및 오류 응답 구조를 정의합니다.

PCAG 파이프라인 위치:
  전체 시스템 공통 (Cross-cutting)

관련 문서:
  - plans/PCAG_Schema_Definitions.md §2.1
"""

from pydantic import BaseModel, Field
from typing import Optional, Any

class ErrorDetail(BaseModel):
    """
    표준 오류 상세 구조.
    
    오류에 대한 기계 판독 가능한 코드와 사람이 읽을 수 있는 메시지를 포함합니다.
    """
    code: str  # 오류 코드 (예: "VALIDATION_ERROR", "INTERNAL_ERROR") — 클라이언트가 에러 유형을 식별하는 데 사용
    message: str  # 사람이 읽을 수 있는 오류 메시지 — 로그나 UI 표시용
    details: Optional[dict[str, Any]] = None  # 추가 컨텍스트 정보 (예: 실패한 필드명, 스택 트레이스 등)

class ErrorResponse(BaseModel):
    """
    표준 API 오류 응답 래퍼.
    
    모든 PCAG 서비스의 오류 응답은 이 형식을 따릅니다.
    """
    error: ErrorDetail  # 실제 오류 상세 객체
