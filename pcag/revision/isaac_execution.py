"""Persistent virtual robot execution. Separate from the restoring safety rollout.

The controller applies joint setpoints then advances the Isaac physics clock.
Completed means the fixed simulation horizon ended; it is not a hardware ACK or
an assertion of trajectory convergence. Ambiguous accepted operations never rerun.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from pcag.revision.durable_json import publish_durable_json


def _path(transaction_id):
    base = Path(os.environ["PCAG_REVISION_RECEIPT_DIR"])
    base.mkdir(parents=True, exist_ok=True)
    return base / (hashlib.sha256(transaction_id.encode()).hexdigest() + ".json")


def _save(path, receipt):
    publish_durable_json(path, receipt, ensure_ascii=False)


def query_operation(transaction_id, asset_id):
    path = _path(transaction_id)
    if not path.exists():
        return {"status": "UNKNOWN", "transaction_id": transaction_id, "asset_id": asset_id, "accepted": False, "completed": False, "ack_boundary": "no_durable_receipt"}
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt["asset_id"] != asset_id:
        raise ValueError("Operation key belongs to another asset")
    if receipt["status"] == "ACCEPTED":
        receipt = {**receipt, "status": "UNKNOWN", "completed": False}
    return receipt


def collect_sample(robot, step, t_s):
    from pcag.plugins.simulation.isaac_collision import get_end_effector_position
    joints = [float(x) for x in robot.get_joint_positions()]
    try:
        efforts = [float(x) for x in robot.get_measured_joint_efforts()]
    except Exception:
        efforts = None
    ee = get_end_effector_position(robot)
    return {"step": step, "t_s": t_s, "joint_positions": joints, "joint_efforts": efforts, "ee_position": None if ee is None else [float(x) for x in ee], "contacts": [], "contact_observer": "not_instrumented"}


def execute_operation(world, robot, job, headless):
    import numpy as np
    tx, asset, actions = job["transaction_id"], job["asset_id"], job["action_sequence"]
    digest = hashlib.sha256(json.dumps({"asset_id": asset, "action_sequence": actions}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    path = _path(tx)
    if path.exists():
        receipt = query_operation(tx, asset)
        if receipt["payload_digest"] != digest:
            raise ValueError("Operation key payload mismatch")
        return receipt
    # Validate the command grammar before storing acceptance or mutating the world.
    joint_count = len(robot.get_joint_positions())
    for action in actions:
        target = (action.get("params") or {}).get("target_positions")
        if action.get("action_type") != "move_joint" or not isinstance(target, list) or not target or len(target) > joint_count or not all(np.isfinite(float(x)) for x in target):
            raise ValueError("Unsupported or invalid virtual robot action")
    receipt = {"status": "ACCEPTED", "transaction_id": tx, "asset_id": asset, "payload_digest": digest, "accepted": True, "completed": False, "accepted_at_ms": int(time.time() * 1000), "ack_boundary": "isaac_persistent_setpoint_physics_horizon", "dispatch_count": 1}
    _save(path, receipt)
    samples = [collect_sample(robot, 0, 0.0)]
    try:
        for action in actions:
            target = np.array(robot.get_joint_positions(), copy=True)
            commanded = action["params"]["target_positions"]
            target[:len(commanded)] = commanded
            robot.set_joint_positions(target)
            for _ in range(int(job.get("steps_per_action", 30))):
                world.step(render=not headless)
                samples.append(collect_sample(robot, len(samples), len(samples) / 60.0))
        receipt.update(status="COMPLETED", completed=True, completed_at_ms=int(time.time() * 1000), final_state=samples[-1], raw_trace={"schema": "pcag.raw-trace.v1", "asset_family": "robot", "complete": True, "expected_samples": len(samples), "samples": samples, "scope": "policy_end_effector_sphere_vs_AABB", "contact_observer": "not_instrumented"})
        _save(path, receipt)
        return receipt
    except Exception as exc:
        receipt.update(status="UNKNOWN", reason=str(exc), completed=False)
        _save(path, receipt)
        raise
