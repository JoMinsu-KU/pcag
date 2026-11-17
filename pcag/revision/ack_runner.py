"""Repeated end-to-end Gateway latency with inspected executor ACK boundaries.

Use separate owned-service configurations/runs for mock and actual virtual ACKs.
This runner never changes the executor configuration or silently falls back.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

import httpx

from tests.revision.baseline_runner import (GatewayDriver, ServiceSettings, create_manifest,
    prepare_manifest, execute, digest, file_sha, DEFAULT_POLICY)


class AckDriver(GatewayDriver):
    def __init__(self, *args, expected_boundary, ot_url, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_boundary, self.ot_url = expected_boundary, ot_url.rstrip("/")

    def run_case(self, task, case, dataset):
        result = super().run_case(task, case, dataset)
        try:
            operation = self.get(self.ot_url + "/v1/operations/" + result["transaction_id"])
            result["operation_observation"] = operation
            boundary = operation.get("ack_boundary") or (operation.get("receipt") or {}).get("ack_boundary")
            result["ack_boundary_matches"] = boundary == self.expected_boundary
            if result["observed"]["status"] == "COMMITTED" and not result["ack_boundary_matches"]:
                result["infrastructure_error"] = f"Expected ACK boundary {self.expected_boundary}, observed {boundary}"
        except Exception as exc:
            result["operation_observation_error"] = repr(exc)
            result["infrastructure_error"] = result["infrastructure_error"] or "Executor ACK receipt could not be inspected"
        result["protocol_valid"] = not bool(result["infrastructure_error"])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--case-ids", type=Path, required=True, help="Frozen JSON list, chosen before evaluating Gateway results")
    parser.add_argument("--repeats", type=int, required=True)
    parser.add_argument("--ack-profile", choices=["mock", "isaac", "modbus_tcp"], required=True)
    parser.add_argument("--executor-config", type=Path, required=True, help="Exact config loaded by the owned OT service")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("Positive repeats required")
    cases = json.loads(args.case_ids.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases or len(cases) != len(set(cases)):
        parser.error("case-ids must be a unique nonempty list")
    settings = ServiceSettings.from_environment()
    manifest = create_manifest(args.dataset, args.policy, profiles=["B5"], seeds=list(range(7000, 7000+args.repeats)), settings=settings, case_ids=cases)
    boundary = {"mock":"mock_ack", "isaac":"isaac_persistent_setpoint_physics_horizon", "modbus_tcp":"modbus_tcp_write_response"}[args.ack_profile]
    manifest["identity"]["ack_experiment"] = {"profile":args.ack_profile, "expected_ack_boundary":boundary,
        "executor_config_path":str(args.executor_config.resolve()), "executor_config_sha256":file_sha(args.executor_config),
        "case_ids_sha256":file_sha(args.case_ids), "repeat_interpretation":"Repeated measurements of fixed cases, not additional independent cases",
        "physical_hardware":False, "latency_boundary":"Gateway POST send to response complete; preparation, preload, reset and receipt query excluded"}
    manifest["manifest_id"] = digest(manifest["identity"])
    manifest = prepare_manifest(args.output_dir / "manifest.json", manifest, resume=args.resume)
    if not args.execute:
        print(json.dumps({"manifest_id":manifest["manifest_id"], "planned":len(manifest["identity"]["tasks"]), "state":"FROZEN_NOT_EXECUTED"}))
        return
    if os.environ.get("PCAG_REVISION_MODE") != "true":
        raise RuntimeError("Revision mode must be explicitly enabled")
    if file_sha(args.executor_config) != manifest["identity"]["ack_experiment"]["executor_config_sha256"]:
        raise RuntimeError("Executor config changed")
    with httpx.Client() as client:
        result = execute(manifest, args.output_dir, AckDriver(client, settings, manifest, expected_boundary=boundary, ot_url=os.environ.get("PCAG_OT_URL", "http://127.0.0.1:18004")))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
