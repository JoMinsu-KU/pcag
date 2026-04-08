"""
Safety Cluster HTTP routes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pcag.apps.safety_cluster.service import run_safety_validation
from pcag.core.contracts.safety import (
    ConsensusDetailsResponse,
    RuntimePreloadRequest,
    RuntimePreloadResponse,
    SafetyValidateRequest,
    SafetyValidateResponse,
    ValidatorVerdictResponse,
)

router = APIRouter(prefix="/v1", tags=["SafetyCluster"])


@router.post("/validate")
def validate(request: SafetyValidateRequest) -> SafetyValidateResponse:
    action_seq = []
    if request.action_sequence:
        for action in request.action_sequence:
            if hasattr(action, "model_dump"):
                action_seq.append(action.model_dump())
            elif hasattr(action, "dict"):
                action_seq.append(action.dict())
            else:
                action_seq.append(action)

    result = run_safety_validation(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id,
        policy_version_id=request.policy_version_id,
        action_sequence=action_seq,
        current_sensor_snapshot=request.current_sensor_snapshot,
        runtime_context=request.runtime_context,
    )

    return SafetyValidateResponse(
        transaction_id=result["transaction_id"],
        final_verdict=result["final_verdict"],
        validators={
            name: ValidatorVerdictResponse(
                verdict=value["verdict"],
                details=value.get("details", {}),
            )
            for name, value in result["validators"].items()
        },
        consensus_details=ConsensusDetailsResponse(
            mode=result["consensus_details"]["mode"],
            weights_used=result["consensus_details"].get("weights_used"),
            score=result["consensus_details"].get("score"),
            threshold=result["consensus_details"].get("threshold"),
            explanation=result["consensus_details"].get("explanation", ""),
        ),
    )


@router.post("/runtime/preload")
def preload_runtime(request: RuntimePreloadRequest) -> RuntimePreloadResponse:
    from pcag.apps.safety_cluster.main import get_isaac_backend

    isaac = get_isaac_backend()
    if not isaac:
        raise HTTPException(status_code=503, detail="Isaac Sim backend not configured")
    if not isaac.is_initialized():
        raise HTTPException(status_code=503, detail="Isaac Sim worker not ready")

    try:
        result = isaac.preload_runtime(
            runtime_context=request.runtime_context,
            initial_state=request.initial_state,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime preload failed: {exc}") from exc

    return RuntimePreloadResponse(
        asset_id=request.asset_id,
        status=result.get("status", "READY"),
        runtime_id=result.get("runtime_id"),
        scene_path=result.get("scene_path"),
        shell_config_path=result.get("shell_config_path"),
        robot_spawn_position=result.get("robot_spawn_position"),
        applied_initial_joint_positions=result.get("applied_initial_joint_positions"),
        current_state=result.get("current_state"),
    )


@router.get("/simulation/state")
def get_simulation_state():
    from pcag.apps.safety_cluster.main import get_isaac_backend

    isaac = get_isaac_backend()
    if not isaac:
        return {"error": "Isaac Sim not configured"}
    if not isaac.is_initialized():
        return {"error": "Isaac Sim worker not ready"}
    return isaac.get_current_state()
