"""Controlled real-state mutation after PREPARE, with timing witnesses.

The revision-only pause hook is instrumentation, not an artificial hash fault.
Every trial records actual state write/readback and evidence timestamps. A trial
whose ordering cannot be established is INCONCLUSIVE rather than a success.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import time
from typing import Any, Mapping

import httpx

from .cohort import _write_once
from .independent import canonical_sha256


def verify_drift_witness(*, before_hash: str, after_hash: str, prepare_timestamp_ms: int|None,
                         mutation_started_ms: int, mutation_completed_ms: int,
                         terminal_timestamp_ms: int|None, terminal_stage: str|None) -> dict[str,Any]:
    """Fail closed on timing ambiguity; wall-clock timestamps are one-host only."""
    changed=before_hash!=after_hash
    ordered=(prepare_timestamp_ms is not None and terminal_timestamp_ms is not None
             and prepare_timestamp_ms <= mutation_started_ms <= mutation_completed_ms <= terminal_timestamp_ms)
    if not changed or not ordered:
        return {"witness":"INCONCLUSIVE","state_hash_changed":changed,"ordering_verified":ordered,
                "reason":"actual state change and PREPARE<write/readback<reverify ordering are both required"}
    return {"witness":"VALID","state_hash_changed":True,"ordering_verified":True,
            "reverify_blocked":terminal_stage=="REVERIFY_FAILED"}


def run_drift_trial(case: Mapping[str,Any], changed_state: Mapping[str,Any], *,
        output_dir: str|Path, client: httpx.Client|None=None, pause_after_prepare_ms=2000,
        gateway_url="http://127.0.0.1:18000", policy_url="http://127.0.0.1:18002",
        sensor_url="http://127.0.0.1:18003", evidence_url="http://127.0.0.1:18005",
        plc_url="http://127.0.0.1:18007", safety_url="http://127.0.0.1:18001",
        api_key="pcag-agent-key-001", poll_seconds=.02, deadline_seconds=30.,
        disable_reverify=False) -> dict[str,Any]:
    """Mutate simulator/Modbus-backed state, never the sensor hash itself."""
    if not 1 <= pause_after_prepare_ms <= 3000:
        raise ValueError("revision pause must be 1..3000 ms")
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    tx="rev-drift-"+canonical_sha256({"case":case,"changed_state":changed_state,
                                  "disable_reverify":disable_reverify,"output_dir":str(out.resolve())})[:28]
    result_path=out/(tx+".json")
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))
    attempt_path=out/(tx+".attempt.json")
    if attempt_path.exists():
        raise RuntimeError(f"incomplete drift attempt {tx}; reconcile its retained transaction before any state mutation replay")
    owned=client is None
    client=client or httpx.Client(timeout=120.)
    try:
        target=safety_url if case["asset_family"]=="robot" else plc_url
        preloaded=client.post(target+"/v1/runtime/preload",json={"asset_id":case["asset_id"],
            "runtime_context":case["runtime_context"],"initial_state":case["initial_state"]})
        preloaded.raise_for_status()
        snapshot=client.get(sensor_url+f"/v1/assets/{case['asset_id']}/snapshots/latest");snapshot.raise_for_status();before=snapshot.json()
        active=client.get(policy_url+"/v1/policies/active");active.raise_for_status()
        proof={"schema_version":"1.0","policy_version_id":active.json()["policy_version_id"],
            "timestamp_ms":int(time.time()*1000),"sensor_snapshot_hash":before["sensor_snapshot_hash"],
            "sensor_snapshot":before["sensor_snapshot"],"sensor_reliability_index":.95,
            "action_sequence":case["action_sequence"],"safety_verification_summary":{},
            "runtime_context":case["runtime_context"],"proof_origin":"revision_actual_state_drift",
            "revision_profile":"B4" if disable_reverify else "B5",
            "revision_test_control":{"pause_after_prepare_ms":pause_after_prepare_ms,"case_token":tx}}
        body={"transaction_id":tx,"asset_id":case["asset_id"],"proof_package":proof}
        _write_once(attempt_path,{"transaction_id":tx,"case_id":case["case_id"],"request_body":body,
            "before_snapshot":before,"changed_state":dict(changed_state),"created_ms":int(time.time()*1000),
            "incomplete_attempt_policy":"reconcile existing transaction; never replay mutation automatically"})
        prepare_event=None
        evidence=None
        mutation=None
        mutation_started=None
        mutation_completed=None
        after=before
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(client.post,gateway_url+"/v1/control-requests",json=body,headers={"X-API-Key":api_key})
            deadline=time.monotonic()+deadline_seconds
            while time.monotonic()<deadline:
                response=client.get(evidence_url+f"/v1/transactions/{tx}")
                if response.status_code==200:
                    evidence=response.json()
                    prepare_event=next((x for x in evidence.get("events",[]) if x.get("stage")=="PREPARE_LOCK_GRANTED"),None)
                    if prepare_event:
                        break
                if future.done():
                    break
                time.sleep(poll_seconds)
            if prepare_event:
                mutation_started=int(time.time()*1000)
                if case["asset_family"]=="robot":
                    mutation_response=client.post(safety_url+"/v1/revision/state",json={"initial_state":dict(changed_state)},
                        headers={"X-API-Key":api_key})
                else:
                    mutation_response=client.post(plc_url+"/v1/runtime/preload",json={"asset_id":case["asset_id"],
                        "runtime_context":case["runtime_context"],"initial_state":dict(changed_state)})
                mutation_response.raise_for_status()
                mutation=mutation_response.json()
                snapshot=client.get(sensor_url+f"/v1/assets/{case['asset_id']}/snapshots/latest");snapshot.raise_for_status();after=snapshot.json()
                mutation_completed=int(time.time()*1000)
            gateway_response=future.result(timeout=deadline_seconds+120.)
        for _ in range(20):
            response=client.get(evidence_url+f"/v1/transactions/{tx}")
            if response.status_code==200:
                evidence=response.json()
                stages={x.get("stage") for x in evidence.get("events",[])}
                if stages & {"REVERIFY_FAILED","REVERIFY_PASSED","COMMIT_ACK","SAFETY_UNSAFE","INTEGRITY_REJECTED"}:
                    break
            time.sleep(poll_seconds)
        events=(evidence or {}).get("events",[])
        terminal=next((x for x in events if x.get("stage") in {"REVERIFY_FAILED","REVERIFY_PASSED"}),None)
        if terminal is None and disable_reverify:
            terminal=next((x for x in events if x.get("stage")=="COMMIT_ACK"),None)
        witness=verify_drift_witness(before_hash=before["sensor_snapshot_hash"],after_hash=after["sensor_snapshot_hash"],
            prepare_timestamp_ms=prepare_event.get("timestamp_ms") if prepare_event else None,
            mutation_started_ms=mutation_started or 0,mutation_completed_ms=mutation_completed or 0,
            terminal_timestamp_ms=terminal.get("timestamp_ms") if terminal else None,
            terminal_stage=terminal.get("stage") if terminal else None)
        record={"schema_version":"pcag.actual-state-drift.v1","transaction_id":tx,"case_id":case["case_id"],
            "asset_family":case["asset_family"],"request_body":body,"before_snapshot":before,"after_snapshot":after,
            "requested_changed_state":deepcopy(dict(changed_state)),"mutation_response":mutation,
            "mutation_started_ms":mutation_started,"mutation_completed_ms":mutation_completed,
            "gateway_http_status":gateway_response.status_code,"gateway_response":gateway_response.json(),
            "evidence":evidence,"witness":witness,"disable_reverify":disable_reverify,
            "pause_is_test_instrumentation_not_latency_measurement":True,
            "outcome":"INCONCLUSIVE" if witness["witness"]!="VALID" else "OBSERVED"}
        _write_once(result_path,record)
        return record
    finally:
        if owned:client.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case",type=Path,required=True,help="JSON containing one self-contained cohort case")
    parser.add_argument("--changed-state",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--pause-after-prepare-ms",type=int,default=2000)
    parser.add_argument("--disable-reverify",action="store_true")
    parser.add_argument("--gateway-url",default="http://127.0.0.1:18000")
    parser.add_argument("--policy-url",default="http://127.0.0.1:18002")
    parser.add_argument("--sensor-url",default="http://127.0.0.1:18003")
    parser.add_argument("--evidence-url",default="http://127.0.0.1:18005")
    parser.add_argument("--plc-url",default="http://127.0.0.1:18007")
    parser.add_argument("--safety-url",default="http://127.0.0.1:18001")
    args=parser.parse_args()
    record=run_drift_trial(json.loads(args.case.read_text(encoding="utf-8")),json.loads(args.changed_state.read_text(encoding="utf-8")),
        output_dir=args.output_dir,pause_after_prepare_ms=args.pause_after_prepare_ms,disable_reverify=args.disable_reverify,
        gateway_url=args.gateway_url,policy_url=args.policy_url,sensor_url=args.sensor_url,evidence_url=args.evidence_url,
        plc_url=args.plc_url,safety_url=args.safety_url)
    print(json.dumps({"transaction_id":record["transaction_id"],"witness":record["witness"],"gateway_response":record["gateway_response"]},ensure_ascii=False))


if __name__=="__main__":main()
