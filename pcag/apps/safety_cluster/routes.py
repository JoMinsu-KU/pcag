"""
Safety Cluster HTTP routes.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pcag.core.middleware.auth import verify_api_key
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
    if request.revision_enabled_validators is not None and os.environ.get("PCAG_REVISION_MODE", "").lower() not in {"true", "1", "yes"}:
        raise HTTPException(status_code=403, detail="Validator subsets require PCAG_REVISION_MODE")
    action_seq = []
    if request.action_sequence:
        for action in request.action_sequence:
            if hasattr(action, "model_dump"):
                action_seq.append(action.model_dump())
            elif hasattr(action, "dict"):
                action_seq.append(action.dict())
            else:
                action_seq.append(action)

    revision_kwargs = {}
    if request.revision_enabled_validators is not None:
        revision_kwargs["revision_enabled_validators"] = request.revision_enabled_validators
    result = run_safety_validation(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id,
        policy_version_id=request.policy_version_id,
        action_sequence=action_seq,
        current_sensor_snapshot=request.current_sensor_snapshot,
        runtime_context=request.runtime_context,
        **revision_kwargs,
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
        enabled_validators=result.get("enabled_validators", ["rules", "cbf", "simulation"]),
        validator_runtime_ms=result.get("validator_runtime_ms", {}),
        validation_wall_ms=result.get("validation_wall_ms"),
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


def _revision_backend():
    if os.environ.get("PCAG_REVISION_MODE", "").lower() not in {"true", "1", "yes"}:
        raise HTTPException(status_code=403, detail="Revision execution is disabled")
    from pcag.apps.safety_cluster.main import get_isaac_backend

    backend = get_isaac_backend()
    if not backend or not backend.is_initialized():
        raise HTTPException(status_code=503, detail="Isaac revision worker is not ready")
    return backend


@router.post("/revision/execute")
def revision_execute(payload: dict, _key: str = Depends(verify_api_key)):
    """Dedicated revision plant-execution path, distinct from validation rollout."""
    backend = _revision_backend()
    return backend.revision_rpc("REVISION_EXECUTE", payload)


@router.get("/revision/operation")
def revision_operation(transaction_id: str, asset_id: str = "robot_arm_01", _key: str = Depends(verify_api_key)):
    backend = _revision_backend()
    return backend.revision_rpc("REVISION_QUERY", {"transaction_id": transaction_id, "asset_id": asset_id})


@router.post("/revision/state")
def revision_set_state(payload: dict, _key: str = Depends(verify_api_key)):
    backend = _revision_backend()
    return backend.revision_rpc("REVISION_SET_STATE", payload)


@router.post("/revision/rollout")
def revision_rollout(payload: dict, _key: str = Depends(verify_api_key)):
    """Collect full step samples for the independent revision evaluator."""
    backend = _revision_backend()
    constraints = dict(payload.get("constraints") or {})
    context = payload.get("runtime_context") or constraints.get("runtime_context")
    if context is not None:
        constraints["runtime_context"] = context
    if payload.get("simulation_config") is not None:
        from pcag.plugins.simulation.isaac_runtime_shell import build_runtime_sim_config
        effective = build_runtime_sim_config(payload["simulation_config"], context)
        for field in ["world_ref", "workspace_limits", "torque_limits", "joint_limits", "collision"]:
            if field not in constraints and field in effective:
                constraints[field] = effective[field]
    if payload.get("restore_after", True) is not True:
        raise HTTPException(status_code=422, detail="Revision validation rollout must restore plant state")
    constraints["revision_collect_trace"] = True
    result = backend.validate_trajectory(
        current_state=payload["current_state"],
        action_sequence=payload["action_sequence"],
        constraints=constraints,
    )
    return {"trace": (result.get("details") or {}).get("raw_trace"), "result": result}
