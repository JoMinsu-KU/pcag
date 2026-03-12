"""
안전 검증 클러스터 (Safety Cluster) — 실제 구현
=================================================
3개의 이질적 검증기를 실행하고 SIL 기반 합의로 최종 판정합니다.

검증기:
  [121] Rules Validator — 결정론적 규칙 검사
  [122] CBF Safety Filter — 안전 여유(barrier) 계산
  [123] Simulation Validator — 미래 궤적 예측 (현재: None 플러그인)
  [124] Consensus Engine — SIL 기반 합의 (AND/WEIGHTED/WORST_CASE)

API:
  POST /v1/validate — 안전 검증 수행

conda pcag 환경에서 실행.
"""
from fastapi import APIRouter
from pcag.core.contracts.safety import (
    SafetyValidateRequest, SafetyValidateResponse,
    ValidatorVerdictResponse, ConsensusDetailsResponse
)
from pcag.apps.safety_cluster.service import run_safety_validation

router = APIRouter(prefix="/v1", tags=["SafetyCluster"])


@router.post("/validate")
def validate(request: SafetyValidateRequest):
    """
    안전 검증 수행 — 실제 3개 검증기 + Consensus 실행
    
    Gateway Core에서 호출됩니다.
    Policy Store에서 AssetPolicyProfile을 조회하여 검증기 설정을 가져옵니다.
    """
    # action_sequence가 Pydantic 모델 리스트일 경우 dict로 변환
    action_seq = []
    if request.action_sequence:
        for a in request.action_sequence:
            if hasattr(a, "model_dump"):
                action_seq.append(a.model_dump())
            elif hasattr(a, "dict"):
                action_seq.append(a.dict())
            else:
                action_seq.append(a)

    result = run_safety_validation(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id,
        policy_version_id=request.policy_version_id,
        action_sequence=action_seq,
        current_sensor_snapshot=request.current_sensor_snapshot
    )
    
    return SafetyValidateResponse(
        transaction_id=result["transaction_id"],
        final_verdict=result["final_verdict"],
        validators={
            k: ValidatorVerdictResponse(
                verdict=v["verdict"],
                details=v.get("details", {})
            )
            for k, v in result["validators"].items()
        },
        consensus_details=ConsensusDetailsResponse(
            mode=result["consensus_details"]["mode"],
            weights_used=result["consensus_details"].get("weights_used"),
            score=result["consensus_details"].get("score"),
            threshold=result["consensus_details"].get("threshold"),
            explanation=result["consensus_details"].get("explanation", "")
        )
    )


@router.get("/simulation/state")
def get_simulation_state():
    """Isaac Sim 현재 상태 조회 (Digital Twin)"""
    # 순환 참조 방지 위해 함수 내부 import
    from pcag.apps.safety_cluster.main import get_isaac_backend
    
    isaac = get_isaac_backend()
    if not isaac:
        return {"error": "Isaac Sim not configured"}
        
    if not isaac.is_initialized():
        return {"error": "Isaac Sim worker not ready"}
    
    return isaac.get_current_state()
