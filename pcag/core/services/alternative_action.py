"""
Alternative action proposal service.

The first implementation is intentionally deterministic and policy-based.
It derives fallback actions from the asset execution policy rather than
calling an external planner or model.
"""

from typing import Any


def generate_alternative_actions(asset_profile: dict | None, reason_code: str | None = None) -> list[dict[str, Any]]:
    """
    Build conservative fallback actions from policy execution.safe_state.

    Args:
        asset_profile: Asset policy profile loaded from Policy Store.
        reason_code: Optional machine-readable reason for the failure path.

    Returns:
        List of action proposal dictionaries safe to serialize in responses
        and evidence payloads.
    """
    if not asset_profile:
        return []

    execution = asset_profile.get("execution", {}) or {}
    safe_state = execution.get("safe_state", []) or []

    proposals: list[dict[str, Any]] = []
    for idx, action in enumerate(safe_state):
        if not isinstance(action, dict):
            continue

        proposals.append(
            {
                "proposal_id": f"safe-state-{idx}",
                "action_type": action.get("action_type", "unknown"),
                "params": action.get("params", {}),
                "rationale": f"Derived from policy execution.safe_state for {reason_code or 'fallback'}",
                "source": "policy.safe_state",
            }
        )

    return proposals
