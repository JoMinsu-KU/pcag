"""Resumable independent shadow rollouts; freeze labels before admission runs.

Robot observations come from the restoring revision rollout RPC. Process and
AGV observations come from explicit ODE/grid models without calling any PCAG
validator. The independent checker reads only full samples and numeric limits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
from typing import Any, Mapping

import httpx

from .cohort import generate_cohort, write_cohort, freeze_labels, _write_once
from .independent import TRACE_SCHEMA, assess_trace, constraints_from_policy, canonical_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = PROJECT_ROOT/"tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json"
COLLECTOR_VERSION = "pcag.raw-shadow-collector.v1"


def deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        result = deepcopy(base)
        for key, value in patch.items():
            result[key] = deep_merge(result.get(key), value)
        return result
    return deepcopy(patch)


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT/path


def resolve_simulation_config(profile: Mapping[str, Any], runtime_context: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve declared shell geometry/parameters without importing validators."""
    config = deepcopy(dict(profile.get("simulation", {})))
    if not runtime_context:
        return config
    shell_path = _project_path(runtime_context["shell_config_ref"])
    shell = json.loads(shell_path.read_text(encoding="utf-8"))
    config = deep_merge(config, shell.get("simulation_patch") or {})
    config = deep_merge(config, runtime_context.get("simulation_override") or {})
    scene = runtime_context.get("scene_ref")
    if scene:
        config["world_ref"] = str(_project_path(scene))
    probe = shell.get("safety_probe") or {}
    if probe:
        collision = deepcopy(config.get("collision") or {})
        collision.setdefault("enabled", True)
        collision["probe_radius_m"] = probe.get("end_effector_probe_radius", .045)
        objects = {x["id"]: x for x in shell.get("runtime_physics_objects", [])}
        collision["forbidden_objects"] = [{"object_id": key, "center": objects[key]["center"],
            "scale": objects[key]["scale"]} for key in probe.get("forbidden_fixture_ids", []) if key in objects]
        collision["allowed_contact_ids"] = list(probe.get("allowed_support_ids", []))
        config["collision"] = collision
    return config


def _trace(family: str, samples: list[dict[str, Any]], **metadata: Any) -> dict[str, Any]:
    return {"schema_version": TRACE_SCHEMA, "asset_family": family, "complete": True,
            "expected_samples": len(samples), "samples": samples, **metadata}


def collect_process_trace(case: Mapping[str, Any], simulation_config: Mapping[str, Any]) -> dict[str, Any]:
    """Integrate every declared action segment; no threshold stops or verdicts."""
    from scipy.integrate import solve_ivp
    import numpy as np
    params = simulation_config["params"]
    keys = ["mass_kg", "specific_heat_j_kg_k", "heater_max_power_w", "heat_transfer_coeff_w_k",
            "coolant_temp_c", "ambient_temp_c", "loss_coeff_w_k", "pressure_coeff_atm_k"]
    if any(key not in params or not math.isfinite(float(params[key])) for key in keys):
        raise ValueError("all declared process parameters must be finite")
    if float(params["mass_kg"]) <= 0 or float(params["specific_heat_j_kg_k"]) <= 0:
        raise ValueError("thermal mass and specific heat must be positive")
    initial = case["initial_state"]
    temperature, pressure = float(initial["temperature"]), float(initial["pressure"])
    heater, cooling = float(initial["heater_output"])/100., float(initial["cooling_valve"])/100.
    step_ms = int(case.get("execution_parameters", {}).get("dt_ms", simulation_config.get("dt_ms", 100)))
    if step_ms <= 0:
        raise ValueError("process sample interval must be positive")
    samples = [{"step": 0, "t_s": 0., "temperature": temperature, "pressure": pressure,
                "heater_output": heater*100., "cooling_valve": cooling*100.}]
    elapsed = 0.
    actions = case["action_sequence"]
    for action in actions:
        kind, value = action["action_type"], float(action["params"]["value"])
        if kind == "set_heater_output":
            heater = value/100.
        elif kind == "set_cooling_valve":
            cooling = value/100.
        else:
            raise ValueError(f"unsupported process action: {kind}")
        duration_ms = max(int(action.get("duration_ms", simulation_config.get("horizon_ms", 5000)/max(len(actions),1))), step_ms)
        duration = duration_ms/1000.
        n = max(round(duration_ms/step_ms), 1)
        def rhs(t, state):
            temp, pres = state
            power = heater*float(params["heater_max_power_w"])
            coolant = cooling*float(params["heat_transfer_coeff_w_k"])*(temp-float(params["coolant_temp_c"]))
            loss = float(params["loss_coeff_w_k"])*(temp-float(params["ambient_temp_c"]))
            derivative = (power-coolant-loss)/(float(params["mass_kg"])*float(params["specific_heat_j_kg_k"]))
            return [derivative,float(params["pressure_coeff_atm_k"])*derivative]
        solution = solve_ivp(rhs,(0.,duration),[temperature,pressure],t_eval=np.linspace(0.,duration,n+1),
                             method="RK45",rtol=1e-8,atol=1e-10,max_step=step_ms/1000.)
        if not solution.success or len(solution.t) != n+1:
            raise RuntimeError("incomplete ODE solve: "+str(solution.message))
        for i in range(1,len(solution.t)):
            samples.append({"step":len(samples),"t_s":elapsed+float(solution.t[i]),
                "temperature":float(solution.y[0,i]),"pressure":float(solution.y[1,i]),
                "heater_output":heater*100.,"cooling_valve":cooling*100.})
        temperature,pressure = float(solution.y[0,-1]),float(solution.y[1,-1])
        elapsed += duration
    return _trace("process",samples,physical_model="declared_thermal_pressure_ODE",solver="scipy.solve_ivp.RK45",
                  collector_version=COLLECTOR_VERSION,admission_output_used=False)


def collect_agv_trace(case: Mapping[str, Any], simulation_config: Mapping[str, Any]) -> dict[str, Any]:
    """Full grid timeline, including parked peers and every terminal frame."""
    initial = case["initial_state"]
    positions = {name:list(item["position"]) for name,item in (simulation_config.get("agvs") or {}).items()}
    for name,item in initial.items():
        if name.startswith("agv_") and isinstance(item,dict) and "x" in item and "y" in item:
            positions[name] = [float(item["x"]),float(item["y"])]
    if "position_x" in initial and "position_y" in initial:
        positions[case["asset_id"]] = [float(initial["position_x"]),float(initial["position_y"])]
    if not positions:
        raise ValueError("AGV initial positions are required")
    paths = {name:deepcopy(item.get("path",[])) for name,item in (simulation_config.get("agvs") or {}).items()}
    for action in case["action_sequence"]:
        if action["action_type"] != "move_to":
            raise ValueError("unsupported AGV action")
        params = action["params"]
        name = params.get("agv_id",case["asset_id"])
        if name not in positions:
            raise ValueError("commanded AGV is missing an initial position")
        if "path" not in params:
            raise ValueError("independent AGV collection requires an explicit declared path")
        paths[name] = deepcopy(params["path"])
    step_s = float(case.get("execution_parameters",{}).get("event_step_s",1.))
    if not math.isfinite(step_s) or step_s <= 0:
        raise ValueError("AGV timestep must be positive")
    steps = max((len(path) for path in paths.values()),default=0)
    samples = []
    resources = simulation_config.get("resources") or {}
    for step in range(steps+1):
        frame = {}
        for name,start in positions.items():
            path = paths.get(name,[])
            frame[name] = list(start if step == 0 else path[min(step,len(path))-1] if path else start)
        sample = {"step":step,"t_s":step*step_s,"positions":frame}
        if simulation_config.get("resource_capacities"):
            occupancy = {}
            for resource in simulation_config["resource_capacities"]:
                if resource not in resources:
                    raise ValueError("resource cell geometry is required for raw occupancy")
                cells = resources[resource].get("cells",[])
                occupancy[resource] = sorted(name for name,position in frame.items() if position in cells)
            sample["resource_occupancy"] = occupancy
        samples.append(sample)
    return _trace("agv",samples,physical_model="declared_concurrent_grid_path_timeline",
                  collector_version=COLLECTOR_VERSION,admission_output_used=False)


def collect_robot_trace(client: httpx.Client, case: Mapping[str, Any], simulation_config: Mapping[str, Any],
                        *, safety_url: str, api_key: str = "pcag-agent-key-001") -> dict[str, Any]:
    preload = client.post(safety_url+"/v1/runtime/preload",json={"asset_id":case["asset_id"],
        "runtime_context":case["runtime_context"],"initial_state":case["initial_state"]})
    preload.raise_for_status()
    state = preload.json().get("current_state") or case["initial_state"]
    constraints = {key:deepcopy(simulation_config[key]) for key in
        ["world_ref","workspace_limits","torque_limits","joint_limits","collision"] if key in simulation_config}
    constraints["revision_collect_trace"] = True
    response = client.post(safety_url+"/v1/revision/rollout",json={"current_state":state,
        "action_sequence":case["action_sequence"],"constraints":constraints,
        "simulation_config":dict(simulation_config),"runtime_context":case["runtime_context"],"restore_after":True},
        headers={"X-API-Key":api_key})
    response.raise_for_status()
    payload = response.json()
    # Extract raw observations only. Simulator verdict/violation flags are not input to the checker.
    raw = payload.get("trace") or payload.get("raw_trace") or (payload.get("details") or {}).get("raw_trace")
    if raw is None and isinstance(payload.get("result"),dict):
        raw = payload["result"].get("raw_trace") or (payload["result"].get("details") or {}).get("raw_trace")
    if not isinstance(raw,dict):
        raise ValueError("rollout RPC did not provide a complete raw_trace")
    raw = deepcopy(raw)
    if "schema_version" not in raw and "schema" in raw:
        raw["schema_version"] = raw.pop("schema")
    raw.update(collector_version=COLLECTOR_VERSION,admission_output_used=False)
    return raw


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _append(path: Path, record: Mapping[str, Any]) -> None:
    with path.open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+"\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_shadow_cohort(cohort: Mapping[str,Any], policy: Mapping[str,Any], output_dir: str|Path, *,
                      safety_url="http://127.0.0.1:18001", client: httpx.Client|None=None,
                      api_key="pcag-agent-key-001") -> dict[str,Any]:
    """Collect/freeze a cohort. Existing complete case artifacts are resumed."""
    out = Path(output_dir)
    write_cohort(cohort,out)
    policy_hash = canonical_sha256(policy)
    manifest = {"schema_version":"pcag.shadow-run.v1","cohort_proposal_sha256":cohort["proposal_sha256"],
        "policy_sha256":policy_hash,"policy_version_id":policy.get("policy_version_id"),"collector_version":COLLECTOR_VERSION,
        "collector_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "checker_source_sha256":hashlib.sha256(Path(__file__).with_name("independent.py").read_bytes()).hexdigest(),
        "safety_url":safety_url,"gateway_results_used":False}
    _write_once(out/"shadow_run_manifest.json",manifest)
    owned = client is None
    client = client or httpx.Client(timeout=180.)
    assessments = {}
    try:
        for case in cohort["cases"]:
            case_id = case["case_id"]
            raw_path = out/"raw"/(case_id+".json")
            constraints_path = out/"constraints"/(case_id+".json")
            assessment_path = out/"assessments"/(case_id+".json")
            if assessment_path.exists():
                raw, limits, assessment = _json(raw_path),_json(constraints_path),_json(assessment_path)
                if assessment.get("trace_sha256") != canonical_sha256(raw) or assessment.get("constraints_sha256") != canonical_sha256(limits):
                    raise ValueError("stored assessment does not match retained observations/constraints")
                assessments[case_id] = assessment
                continue
            profile = policy["assets"][case["asset_id"]]
            config = resolve_simulation_config(profile,case.get("runtime_context") or {})
            limits = constraints_from_policy(case["asset_family"],profile,simulation_config=config)
            started = time.perf_counter()
            if raw_path.exists():
                raw = _json(raw_path)
            else:
                try:
                    if case["asset_family"] == "robot":
                        raw = collect_robot_trace(client,case,config,safety_url=safety_url,api_key=api_key)
                    elif case["asset_family"] == "agv":
                        raw = collect_agv_trace(case,config)
                    else:
                        raw = collect_process_trace(case,config)
                except Exception as exc:
                    raw = {"schema_version":TRACE_SCHEMA,"asset_family":case["asset_family"],"complete":False,
                           "expected_samples":0,"samples":[],"collection_error":f"{type(exc).__name__}: {exc}",
                           "collector_version":COLLECTOR_VERSION,"admission_output_used":False}
                _write_once(raw_path,raw)
            _write_once(constraints_path,limits)
            assessment = assess_trace(case["asset_family"],raw,limits)
            assessment["collection_wall_ms"] = round((time.perf_counter()-started)*1000.,3)
            _write_once(assessment_path,assessment)
            assessments[case_id] = assessment
            _append(out/"shadow_progress.jsonl",{"case_id":case_id,"intended_class":case["intended_class"],
                "physical_verdict":assessment["verdict"],"completed":len(assessments),"total":len(cohort["cases"]),
                "reason":assessment.get("reason")})
            print(f"[SHADOW] {len(assessments)}/{len(cohort['cases'])} {case_id} -> {assessment['verdict']}",flush=True)
        frozen = freeze_labels(cohort,assessments,out)
        summary = {"cohort_id":cohort["cohort_id"],"cases":len(cohort["cases"]),
            "physical_label_counts":frozen["physical_label_counts"],"label_freeze_sha256":frozen["label_freeze_sha256"],
            "intent_disagreements":sum((x["intended_class"]=="nominal" and x["physical_label"]=="UNSAFE") or
                (x["intended_class"]=="unsafe" and x["physical_label"]=="SAFE") for x in frozen["labels"]),
            "indeterminate":sum(x["physical_label"]=="INDETERMINATE" for x in frozen["labels"]),
            "all_cases_retained":True,"gateway_outputs_used_for_labels":False}
        _write_once(out/"shadow_summary.json",summary)
        return summary
    finally:
        if owned:
            client.close()


def evaluate_frozen_gateway(cohort: Mapping[str,Any], output_dir: str|Path, *, client: httpx.Client|None=None,
        gateway_url="http://127.0.0.1:18000", policy_url="http://127.0.0.1:18002",
        sensor_url="http://127.0.0.1:18003", safety_url="http://127.0.0.1:18001",
        plc_url="http://127.0.0.1:18007", api_key="pcag-agent-key-001",case_interval_seconds=6.) -> dict[str,Any]:
    """Admission is evaluated only against an existing immutable label freeze."""
    out = Path(output_dir)
    frozen = _json(out/"independent_labels_frozen.json")
    if frozen["proposal_sha256"] != cohort["proposal_sha256"]:
        raise ValueError("label freeze belongs to another cohort")
    frozen_content=deepcopy(frozen)
    freeze_hash=frozen_content.pop("label_freeze_sha256")
    if canonical_sha256(frozen_content)!=freeze_hash:
        raise ValueError("independent labels changed after freeze")
    labels = {x["case_id"]:x["physical_label"] for x in frozen["labels"]}
    previous = {}
    progress = out/"gateway_results.jsonl"
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            item=json.loads(line);previous[item["case_id"]]=item
    owned=client is None
    client=client or httpx.Client(timeout=180.)
    try:
        active=client.get(policy_url+"/v1/policies/active");active.raise_for_status()
        version=active.json()["policy_version_id"]
        frozen_policy_version=_json(out/"shadow_run_manifest.json").get("policy_version_id")
        if frozen_policy_version is not None and version!=frozen_policy_version:
            raise ValueError("active policy version differs from the pre-label policy")
        for case in cohort["cases"]:
            case_id=case["case_id"]
            if case_id in previous:
                continue
            if labels[case_id]=="INDETERMINATE":
                record={"case_id":case_id,"physical_label":"INDETERMINATE","status":"NOT_EVALUATED",
                    "reason":"independent physical label unavailable; retained in total denominator"}
            else:
                preload_url=(safety_url if case["asset_family"]=="robot" else plc_url)+"/v1/runtime/preload"
                preload=client.post(preload_url,json={"asset_id":case["asset_id"],"runtime_context":case["runtime_context"],"initial_state":case["initial_state"]})
                preload.raise_for_status()
                snapshot=client.get(sensor_url+f"/v1/assets/{case['asset_id']}/snapshots/latest");snapshot.raise_for_status();snapshot=snapshot.json()
                tx=f"rev-fresh-{canonical_sha256({'case':case_id,'freeze':frozen['label_freeze_sha256']})[:28]}"
                body={"transaction_id":tx,"asset_id":case["asset_id"],"proof_package":{
                    "schema_version":"1.0","policy_version_id":version,"timestamp_ms":int(time.time()*1000),
                    "sensor_snapshot_hash":snapshot["sensor_snapshot_hash"],"sensor_snapshot":snapshot["sensor_snapshot"],
                    "sensor_reliability_index":snapshot.get("sensor_reliability_index",.95),"action_sequence":case["action_sequence"],
                    "safety_verification_summary":{},"runtime_context":case["runtime_context"],
                    "revision_profile":"B5",
                    "agent_id":"revision-frozen-cohort","intent_id":case_id,"proof_origin":"independent_labels_pre_frozen"}}
                start=time.perf_counter()
                try:
                    response=client.post(gateway_url+"/v1/control-requests",json=body,headers={"X-API-Key":api_key})
                    duration=round((time.perf_counter()-start)*1000.,3)
                    payload=response.json();status=payload.get("status","HTTP_ERROR")
                    record={"case_id":case_id,"asset_family":case["asset_family"],"physical_label":labels[case_id],
                        "transaction_id":tx,"http_status":response.status_code,"status":status,"response":payload,
                        "duration_ms":duration,"request_body":body,"label_freeze_sha256":frozen["label_freeze_sha256"]}
                except Exception as exc:
                    record={"case_id":case_id,"asset_family":case["asset_family"],"physical_label":labels[case_id],
                        "transaction_id":tx,"status":"OUTCOME_UNKNOWN","reason":str(exc),
                        "duration_ms":round((time.perf_counter()-start)*1000.,3),"label_freeze_sha256":frozen["label_freeze_sha256"]}
            _append(progress,record);previous[case_id]=record
            if case_interval_seconds>0:
                time.sleep(case_interval_seconds)
        safe=[r for r in previous.values() if r["physical_label"]=="SAFE"]
        unsafe=[r for r in previous.values() if r["physical_label"]=="UNSAFE"]
        latency=[r["duration_ms"] for r in safe if r.get("status")=="COMMITTED"]
        summary={"cohort_id":cohort["cohort_id"],"total":len(cohort["cases"]),"evaluated_or_retained":len(previous),
            "safe_label_count":len(safe),"unsafe_label_count":len(unsafe),
            "safe_noncommit_count":sum(r["status"]!="COMMITTED" for r in safe),
            "unsafe_commit_count":sum(r["status"]=="COMMITTED" for r in unsafe),
            "safe_noncommit_rate":sum(r["status"]!="COMMITTED" for r in safe)/len(safe) if safe else None,
            "status_counts":dict(Counter(r["status"] for r in previous.values())),
            "committed_safe_latency_median_ms":statistics.median(latency) if latency else None,
            "label_freeze_sha256":frozen["label_freeze_sha256"],"case_interval_seconds":case_interval_seconds}
        _write_once(out/"gateway_summary.json",summary)
        return summary
    finally:
        if owned:client.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot",action="store_true")
    parser.add_argument("--cohort",type=Path)
    parser.add_argument("--seed",type=int,default=20261104)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--policy-path",type=Path,default=DEFAULT_POLICY)
    parser.add_argument("--safety-url",default="http://127.0.0.1:18001")
    parser.add_argument("--evaluate-gateway",action="store_true")
    parser.add_argument("--gateway-url",default="http://127.0.0.1:18000")
    parser.add_argument("--policy-url",default="http://127.0.0.1:18002")
    parser.add_argument("--sensor-url",default="http://127.0.0.1:18003")
    parser.add_argument("--plc-url",default="http://127.0.0.1:18007")
    parser.add_argument("--api-key",default=os.environ.get("PCAG_API_KEY_1","pcag-agent-key-001"))
    parser.add_argument("--case-interval-seconds",type=float,default=6.)
    args=parser.parse_args()
    if args.pilot and args.cohort:
        parser.error("choose --pilot or --cohort")
    cohort=_json(args.cohort/"cohort_proposal.json" if args.cohort and args.cohort.is_dir() else args.cohort) if args.cohort else generate_cohort(seed=args.seed,split="pilot" if args.pilot else "main",profile="pilot" if args.pilot else "expanded")
    result=run_shadow_cohort(cohort,_json(args.policy_path),args.output_dir,safety_url=args.safety_url,api_key=args.api_key)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if args.evaluate_gateway:
        print(json.dumps(evaluate_frozen_gateway(cohort,args.output_dir,gateway_url=args.gateway_url,
            policy_url=args.policy_url,sensor_url=args.sensor_url,safety_url=args.safety_url,plc_url=args.plc_url,
            api_key=args.api_key,case_interval_seconds=args.case_interval_seconds),ensure_ascii=False),flush=True)


if __name__=="__main__":main()
