"""EXP-D: repeated independently SAFE commands and separately labeled drift.

Planning is offline. --collect-drift-labels collects independent shadow traces
without Gateway admission. --execute runs the immutable plan. N0 has no injected
pause or mutation; N1 uses the timed real-state drift runner and is excluded
from nominal latency and false-rejection estimates.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Any, Mapping

import httpx

from pcag.revision.cohort import _write_once, write_cohort
from pcag.revision.drift_runner import run_drift_trial
from pcag.revision.independent import canonical_sha256
from pcag.revision.trace_runner import run_shadow_cohort, resolve_simulation_config
from tests.revision.baseline_metrics import latency_summary, observed_triplet
from tests.revision.baseline_runner import (AppendJournal, GatewayDriver, ServiceSettings,
    DEFAULT_POLICY, digest, file_sha, load_json, make_request, prepare_manifest, code_bindings,
    runtime_bindings, ROOT)
from tests.revision.pilot_driver import validate_labels, isolated_settings

LEVELS = {
    "low": {"robot": .0001, "agv": .001, "process": .01},
    "medium": {"robot": .001, "agv": .01, "process": .1},
    "high": {"robot": .01, "agv": .1, "process": 1.},
}
DEFAULT_PERIODS = [.5, 1., 2., 5., 10.]


def _validate_proposal(cohort: Mapping[str, Any]) -> None:
    content=deepcopy(dict(cohort));assigned=content.pop("proposal_sha256",None)
    if canonical_sha256(content)!=assigned:
        raise ValueError("proposal content changed")
    for case in cohort["cases"]:
        payload={key:case[key] for key in ["scenario_family","initial_state","action_sequence","runtime_context","execution_parameters"]}
        if canonical_sha256(payload)!=case["physical_payload_sha256"]:
            raise ValueError("case physical payload changed")


def benign_state(case: Mapping[str, Any], policy: Mapping[str, Any], level: str) -> dict[str, Any]:
    """Propose a boundary-preserving perturbation; this is not a safety label.

    Both original and changed-state action trajectories must independently be
    labeled SAFE before N1 admission. Numeric inclusion alone is insufficient.
    """
    family=case["asset_family"];delta=LEVELS[level][family]
    state=deepcopy(case["initial_state"])
    profile=policy["assets"][case["asset_id"]]
    config=resolve_simulation_config(profile,case["runtime_context"])
    if family=="robot":
        values=state["joint_positions"]
        joint=config["joint_limits"]
        low,high=joint["0"] if isinstance(joint,dict) else joint[0]
        value=float(values[0]);values[0]=value+delta if value+delta<=high else value-delta
        if not low<=values[0]<=high:
            raise ValueError("no in-bound robot drift at requested level")
    elif family=="agv":
        value=float(state["position_x"]);high=float(config["grid"]["width"])-1e-9
        changed=value+delta if value+delta<=high else value-delta
        if changed<0:
            raise ValueError("no in-bound AGV drift at requested level")
        state["position_x"]=changed
        if case["asset_id"] in state:
            state[case["asset_id"]]["x"]=changed
    else:
        rule=next(x for x in profile["ruleset"] if x.get("type")=="range" and x.get("target_field")=="temperature")
        value=float(state["temperature"])
        state["temperature"]=value+delta if value+delta<=rule["max"] else value-delta
        if not rule["min"]<=state["temperature"]<=rule["max"]:
            raise ValueError("no in-bound process drift at requested level")
    return state


def drift_cohort_for(cases: list[dict], parent: Mapping[str, Any], policy: Mapping[str, Any], levels: list[str]) -> dict:
    result={"schema_version":parent["schema_version"],"cohort_id":parent["cohort_id"]+"-exp-d-benign-drift",
        "seed":parent["seed"],"split":parent["split"],"profile":"exp_d_perturbed_safe_candidates",
        "generator_version":"pcag.exp-d-benign-proposal.v1","cases":[],
        "protocol":{"intent_is_not_label":True,"label_source":"independent complete raw-trace assessment",
            "freeze_labels_before_admission":True,"source_proposal_sha256":parent["proposal_sha256"],
            "selection_rule":"all proposed perturbations retained; only independently SAFE original and changed trajectories enter N1 admission"}}
    for original in cases:
        for level in levels:
            case=deepcopy(original)
            case["case_id"]=original["case_id"]+"-benign-"+level
            case["source_case_id"]=original["case_id"]
            case["drift_level"]=level
            case["initial_state"]=benign_state(original,policy,level)
            case["scenario_family"]="benign_state_perturbation_"+level
            case["intended_class"]="nominal"
            case["physical_label_state"]="PENDING_TRACE_ASSESSMENT"
            payload={key:case[key] for key in ["scenario_family","initial_state","action_sequence","runtime_context","execution_parameters"]}
            case["physical_payload_sha256"]=canonical_sha256(payload)
            result["cases"].append(case)
    result["proposal_sha256"]=canonical_sha256(result)
    return result


def normal_dataset(cases: list[dict]) -> dict:
    """Adapter metadata only; preserve all physical command values."""
    rows=[]
    for case in cases:
        context=deepcopy(case["runtime_context"])
        if case["asset_family"]=="agv" and "agv_02" in case["initial_state"]:
            context["sensor_state_overlay"]={"agv_02":deepcopy(case["initial_state"]["agv_02"])}
        rows.append({"case_id":case["case_id"],"asset_id":case["asset_id"],"asset_family":case["asset_family"],
            "case_group":"independently_safe","runtime":{"preload_required":True,
                "preload_target":"safety_cluster" if case["asset_family"]=="robot" else "plc_adapter",
                "sensor_alignment_mode":"latest_after_preload","initial_state":deepcopy(case["initial_state"])},
            "proof":{"action_sequence":deepcopy(case["action_sequence"]),"runtime_context":context,
                "sensor_snapshot_mode":"latest","sensor_hash_mode":"latest"}})
    return {"defaults":{},"libraries":{},"cases":rows}


def create_normal_manifest(cohort_path: Path, labels_path: Path, policy_path: Path, *,
        settings: ServiceSettings, modes: list[str], repeats=10, periods=None, levels=None,
        profiles=None, seed=20261104, case_ids=None, asset_family=None, limit=None,
        allow_pilot=False) -> tuple[dict,dict,dict]:
    cohort,labels,policy=load_json(cohort_path),load_json(labels_path),load_json(policy_path)
    _validate_proposal(cohort)
    label_index=validate_labels(cohort,labels)
    if (labels_path.parent/"run_invalidated.json").exists():
        raise ValueError("independent trace run was invalidated")
    if not allow_pilot and cohort["split"]!="main":
        raise ValueError("EXP-D requires the disjoint main cohort; --allow-pilot is only for debugging")
    if not modes or set(modes)-{"N0","N1"} or len(set(modes))!=len(modes):
        raise ValueError("modes must be unique N0/N1")
    if type(repeats) is not int or repeats<1:
        raise ValueError("repeats must be positive")
    periods=DEFAULT_PERIODS if periods is None else periods
    levels=list(LEVELS) if levels is None else levels
    profiles=["B5"] if profiles is None else profiles
    if not periods or any(not math.isfinite(float(x)) or x<=0 for x in periods) or len(set(periods))!=len(periods):
        raise ValueError("offer periods must be positive and unique")
    if set(levels)-set(LEVELS) or not levels or len(set(levels))!=len(levels):
        raise ValueError("unknown or duplicated drift level")
    if not profiles or set(profiles)-{"B4","B5"} or len(set(profiles))!=len(profiles):
        raise ValueError("normal profiles must be unique B4/B5")
    selected_ids=set(case_ids or [])
    if selected_ids-{x["case_id"] for x in cohort["cases"]}:
        raise ValueError("unknown selected case")
    cases=[x for x in cohort["cases"] if label_index[x["case_id"]]["physical_label"]=="SAFE"
           and (not selected_ids or x["case_id"] in selected_ids)
           and (asset_family is None or x["asset_family"]==asset_family)]
    if limit is not None:
        if limit<1:raise ValueError("limit must be positive")
        cases=cases[:limit]
    if not cases:raise ValueError("no independently SAFE selected cases")
    perturbed=drift_cohort_for(cases,cohort,policy,levels) if "N1" in modes else None
    tasks=[]
    for mode in modes:
        for period in periods:
            for repeat in range(repeats):
                order=list(cases);random.Random(f"{seed}:{mode}:{period}:{repeat}").shuffle(order)
                for case in order:
                    for level in ([None] if mode=="N0" else levels):
                        profile_order=list(profiles);random.Random(f"{seed}:{case['case_id']}:{repeat}:{mode}:{level}").shuffle(profile_order)
                        for profile in profile_order:
                            item={"case_id":case["case_id"],"asset_id":case["asset_id"],"asset_family":case["asset_family"],
                                "mode":mode,"period_s":float(period),"repeat":repeat,"drift_level":level,"profile":profile,
                                "cluster_id":case["case_id"]}
                            item["task_id"]=digest(item)[:24];tasks.append(item)
    core={key:policy.get(key,{}) for key in ["policy_version_id","global_policy","assets"]}
    identity={"schema_version":"pcag.exp-d-normal.v1","cohort_path":str(cohort_path.resolve()),
        "cohort_file_sha256":file_sha(cohort_path),"proposal_sha256":cohort["proposal_sha256"],
        "labels_path":str(labels_path.resolve()),"labels_file_sha256":file_sha(labels_path),
        "label_freeze_sha256":labels["label_freeze_sha256"],"policy_path":str(policy_path.resolve()),
        "policy_file_sha256":file_sha(policy_path),"policy_version_id":policy["policy_version_id"],"policy_core_sha256":digest(core),
        "safe_case_ids":[x["case_id"] for x in cases],"unique_safe_cases":len(cases),
        "unique_safe_by_asset":dict(Counter(x["asset_family"] for x in cases)),
        "claim_minimum_180_unique_safe_met":cohort["split"]=="main" and len(cases)>=180
            and all(sum(x["asset_family"]==family for x in cases)>=60 for family in ["robot","agv","process"]),
        "modes":modes,"repeats":repeats,"periods_s":periods,"drift_levels":levels,"profiles":profiles,
        "tasks":tasks,"services":asdict(settings),"code_sha256":code_bindings(),
        "runtime_artifact_sha256":runtime_bindings(),"perturbed_proposal_sha256":perturbed["proposal_sha256"] if perturbed else None,
        "load_contract":"Serial client; target start-to-start Gateway offer periods. Actual offers/overruns retained; not a concurrent saturation test.",
        "latency_contract":"N0 only: Gateway HTTP send through response. Reset/preload, pacing and evidence fetch excluded. N1 pause trials excluded.",
        "denominator_contract":"N0 noncommit and known gate rejection reported separately from infrastructure/unknown; repeats clustered by unique case. N1 blocking is not false rejection.",
        "drift_label_contract":"N1 needs pre-frozen independently SAFE original and changed-state trajectories; generator benign intent is not a label."}
    return {"manifest_id":digest(identity),"created_at_utc":datetime.now(timezone.utc).isoformat(),"identity":identity},normal_dataset(cases),perturbed


def _verify_manifest(manifest: dict) -> None:
    data=manifest["identity"]
    if digest(data)!=manifest["manifest_id"]:raise ValueError("normal manifest was changed")
    bindings={data["cohort_path"]:data["cohort_file_sha256"],data["labels_path"]:data["labels_file_sha256"],
        data["policy_path"]:data["policy_file_sha256"]}
    bindings.update({str(ROOT/path):sha for group in ["code_sha256","runtime_artifact_sha256"] for path,sha in data[group].items()})
    changed=[path for path,sha in bindings.items() if not Path(path).is_file() or file_sha(Path(path))!=sha]
    if changed:raise RuntimeError(f"frozen normal inputs changed: {changed[:5]}")


class NormalGatewayDriver(GatewayDriver):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.last_offer={}

    def run_no_mutation(self, task: dict, case: dict, dataset: dict) -> dict:
        row={**task,"observed":{"status":None,"stop_stage":None,"reason_code":None},
            "request_duration_ms":None,"infrastructure_error":None,"resource_states":{},"mutation_injected":False,
            "artificial_prepare_pause_ms":0,"physical_label":"SAFE"}
        tx=f"normal-{self.manifest['manifest_id'][:12]}-{task['task_id']}";row["transaction_id"]=tx
        try:
            row["resource_states"]["before"]=self.state(task["asset_id"])
            row["resource_states"]["reset_before"]=self.reset(task["asset_id"],"EXP-D N0 before "+task["task_id"])
            row["preload"]=self.preload(case,dataset)
            active=self.check_policy()
            group=(task["mode"],task["period_s"])
            target=self.last_offer.get(group)
            if target is not None:
                time.sleep(max(0.,target+task["period_s"]-time.monotonic()))
            # Proof/sensor are acquired after pacing, so a 10s period cannot
            # itself manufacture a stale timestamp or sensor hash.
            sensor=self.get(f"{self.settings.sensor}/v1/assets/{task['asset_id']}/snapshots/latest")
            body=make_request(case,dataset,sensor=sensor,active_policy=active,transaction_id=tx,
                profile=task["profile"],now_ms=int(time.time()*1000))
            row["request_body"]=body;row["sensor_after_preload"]=sensor
            began=time.monotonic();row["offer_started_monotonic_s"]=began;row["offer_started_ms"]=int(time.time()*1000)
            row["actual_offer_interval_s"]=began-target if target is not None else None
            row["offer_lateness_s"]=max(0.,began-target-task["period_s"]) if target is not None else None
            self.last_offer[group]=began
            start=time.perf_counter()
            try:
                response=self.client.post(self.settings.gateway+"/v1/control-requests",json=body,headers=self.headers,
                    timeout=self.settings.request_timeout_s)
            finally:row["request_duration_ms"]=(time.perf_counter()-start)*1000.
            row["response_json"]=response.json();row["response_status_code"]=response.status_code
            row["evidence"]=self.get(self.settings.evidence+f"/v1/transactions/{tx}")
            row["observed"]=observed_triplet(row["response_json"],row["evidence"])
            if response.status_code!=200:row["infrastructure_error"]=f"HTTP {response.status_code}"
            elif row["observed"]["reason_code"] in {"REVISION_PIPELINE_ERROR","REVISION_VALIDATOR_MISMATCH","DURABLE_STATE_UNAVAILABLE",
                    "EVIDENCE_TRANSACTION_EXISTS","REVISION_RECONCILIATION_REQUIRED","PAYLOAD_CONFLICT","EXECUTION_OUTCOME_UNKNOWN"}:
                row["infrastructure_error"]="Gateway infrastructure/unknown: "+row["observed"]["reason_code"]
        except Exception as exc:
            row["infrastructure_error"]=f"{type(exc).__name__}: {exc}"
            if row.get("response_json"):row["observed"]=observed_triplet(row["response_json"],row.get("evidence"))
        finally:self._clean_after(task,row)
        row["protocol_valid"]=not bool(row["infrastructure_error"])
        return row

    def _clean_after(self,task,row):
        try:
            row["resource_states"]["after_before_reset"]=self.state(task["asset_id"])
            row["resource_states"]["reset_after"]=self.reset(task["asset_id"],"EXP-D after "+task["task_id"])
            row["resource_states"]["after"]=self.state(task["asset_id"])
            if row["resource_states"]["after"].get("clean") is not True:raise RuntimeError("asset did not reset clean")
        except Exception as exc:
            row["cleanup_error"]=f"{type(exc).__name__}: {exc}"
            row["infrastructure_error"]=row.get("infrastructure_error") or row["cleanup_error"]

    def run_benign_drift(self,task,original,changed,output_dir):
        row={**task,"infrastructure_error":None,"resource_states":{},"mutation_injected":True,
             "observed":{"status":None,"stop_stage":None,"reason_code":None},"request_duration_ms":None,
             "physical_label_original":"SAFE","physical_label_changed":"SAFE","exclude_from_nominal_latency":True}
        try:
            row["resource_states"]["before"]=self.state(task["asset_id"])
            row["resource_states"]["reset_before"]=self.reset(task["asset_id"],"EXP-D N1 before "+task["task_id"])
            self.check_policy()
            group=(task["mode"],task["period_s"])
            previous=self.last_offer.get(group)
            if previous is not None:time.sleep(max(0.,previous+task["period_s"]-time.monotonic()))
            self.last_offer[group]=time.monotonic()
            runtime_case=deepcopy(original)
            if original["asset_family"]=="agv" and "agv_02" in original["initial_state"]:
                runtime_case["runtime_context"]["sensor_state_overlay"]={"agv_02":deepcopy(original["initial_state"]["agv_02"])}
            result=run_drift_trial(runtime_case,changed["initial_state"],output_dir=output_dir,client=self.client,
                gateway_url=self.settings.gateway,policy_url=self.settings.policy,sensor_url=self.settings.sensor,
                evidence_url=self.settings.evidence,plc_url=self.settings.plc_adapter,safety_url=self.settings.safety,
                api_key=self.headers["X-API-Key"],pause_after_prepare_ms=2000,disable_reverify=task["profile"]=="B4")
            row["drift_result"]=result;row["observed"]=observed_triplet(result["gateway_response"],result["evidence"])
            row["witness"]=result["witness"]
            if result["witness"]["witness"]!="VALID":row["infrastructure_error"]="drift synchronization witness is inconclusive"
        except Exception as exc:row["infrastructure_error"]=f"{type(exc).__name__}: {exc}"
        finally:self._clean_after(task,row)
        row["protocol_valid"]=not bool(row["infrastructure_error"])
        return row


def summarize_normal(rows: list[dict], manifest: dict) -> dict:
    groups=defaultdict(list)
    for row in rows:
        key=(row["mode"],row["profile"],row["period_s"],row.get("drift_level"))
        groups[(*key,"all")].append(row)
        groups[(*key,row["asset_family"])].append(row)
    summaries=[]
    for (mode,profile,period,level,asset),items in sorted(groups.items(),key=lambda x:str(x[0])):
        observed=[x for x in items if x.get("status")!="NOT_EVALUATED"]
        committed=lambda x:x.get("observed",{}).get("status")=="COMMITTED"
        known_reject=lambda x:not x.get("infrastructure_error") and x.get("observed",{}).get("status") in {"REJECTED","UNSAFE","ABORTED"}
        clusters=defaultdict(list)
        for item in observed:clusters[item["case_id"]].append(item)
        group={"mode":mode,"profile":profile,"period_s":period,"drift_level":level,"asset_family":asset,"retained_attempts":len(items),
            "admission_attempts":len(observed),"unique_cases":len(clusters),
            "attempts_per_case":dict(Counter(len(x) for x in clusters.values())),
            "not_evaluated_count":len(items)-len(observed),"committed_count":sum(committed(x) for x in observed),
            "noncommit_count":sum(not committed(x) for x in observed),
            "infrastructure_or_unknown_count":sum(bool(x.get("infrastructure_error")) for x in observed),
            "known_gate_rejection_count":sum(known_reject(x) for x in observed),
            "status_counts":dict(Counter(x.get("observed",{}).get("status") or "UNKNOWN" for x in observed))}
        if mode=="N0":
            means=[sum(not committed(x) for x in cluster)/len(cluster) for cluster in clusters.values()]
            group.update(safe_noncommit_rate=group["noncommit_count"]/len(observed) if observed else None,
                known_false_rejection_rate=group["known_gate_rejection_count"]/len(observed) if observed else None,
                case_cluster_mean_noncommit_rate=sum(means)/len(means) if means else None,
                unique_cases_with_any_noncommit=sum(any(not committed(x) for x in cluster) for cluster in clusters.values()),
                latency_committed_safe=latency_summary(x["request_duration_ms"] for x in observed if committed(x) and x.get("request_duration_ms") is not None),
                latency_all_attempts=latency_summary(x["request_duration_ms"] for x in observed if x.get("request_duration_ms") is not None),
                offer_overrun_count=sum((x.get("offer_lateness_s") or 0.)>.01 for x in observed),
                reverify_block_count=sum(x.get("observed",{}).get("reason_code")=="REVERIFY_HASH_MISMATCH" for x in observed),
                independent_unit="unique case; repeats are clustered and are not additional independent nominal cases")
        else:
            valid=[x for x in observed if (x.get("witness") or {}).get("witness")=="VALID"]
            blocks=sum(x.get("observed",{}).get("reason_code")=="REVERIFY_HASH_MISMATCH" for x in valid)
            group.update(valid_actual_drift_witnesses=len(valid),reverify_block_count=blocks,
                blocking_rate_on_valid_drift=blocks/len(valid) if valid else None,
                false_rejection_rate=None,nominal_latency=None,
                interpretation="Both trajectories independently SAFE; binding state change still requires revalidation. Blocking counter is separate from N0 false rejection.")
        summaries.append(group)
    return {"manifest_id":manifest["manifest_id"],"planned_attempts":len(manifest["identity"]["tasks"]),
        "finished_attempts":len(rows),"planned_unique_safe_cases":manifest["identity"]["unique_safe_cases"],
        "claim_minimum_180_unique_safe_met":manifest["identity"]["claim_minimum_180_unique_safe_met"],
        "groups":summaries,"repeat_denominator_warning":"Repeated observations do not increase the independently labeled unique-case denominator."}


def execute_normal(manifest: dict, directory: Path, driver: NormalGatewayDriver, *, max_tasks=None) -> dict:
    journal=AppendJournal(directory/"normal_attempts.jsonl",manifest["manifest_id"])
    if journal.unfinished:raise RuntimeError("unfinished normal task requires reconciliation; no dispatch replay")
    cohort=load_json(Path(manifest["identity"]["cohort_path"]))
    originals={x["case_id"]:x for x in cohort["cases"]}
    selected=[originals[x] for x in manifest["identity"]["safe_case_ids"]]
    dataset=normal_dataset(selected);cases={x["case_id"]:x for x in dataset["cases"]}
    changed={};drift_labels={};drift_hash=None;drift_file_hash=None
    if "N1" in manifest["identity"]["modes"]:
        changed_cohort=load_json(directory/"drift_cohort/cohort_proposal.json")
        drift_file=directory/"drift_independent/independent_labels_frozen.json"
        if not drift_file.exists():raise RuntimeError("collect and freeze changed-state independent labels before N1 execution")
        frozen=load_json(drift_file);drift_labels=validate_labels(changed_cohort,frozen)
        if (drift_file.parent/"run_invalidated.json").exists():raise RuntimeError("changed-state trace run invalidated")
        if changed_cohort["proposal_sha256"]!=manifest["identity"]["perturbed_proposal_sha256"]:raise RuntimeError("changed proposal mismatch")
        changed={(x["source_case_id"],x["drift_level"]):x for x in changed_cohort["cases"]}
        drift_hash=frozen["label_freeze_sha256"]
        drift_file_hash=file_sha(drift_file)
        _write_once(directory/"drift_execution_label_binding.json",{"label_freeze_sha256":drift_hash,"file_sha256":drift_file_hash})
    count=0
    for task in manifest["identity"]["tasks"]:
        if task["task_id"] in journal.completed:continue
        if max_tasks is not None and count>=max_tasks:break
        _verify_manifest(manifest)
        if drift_file_hash is not None and file_sha(drift_file)!=drift_file_hash:
            raise RuntimeError("changed-state labels changed during admission run")
        journal.append("task_started",task,task_spec=task)
        if task["mode"]=="N0":row=driver.run_no_mutation(task,cases[task["case_id"]],dataset)
        else:
            altered=changed[(task["case_id"],task["drift_level"])]
            if drift_labels[altered["case_id"]]["physical_label"]!="SAFE":
                row={**task,"status":"NOT_EVALUATED","reason":"changed-state trajectory was not independently SAFE",
                    "changed_physical_label":drift_labels[altered["case_id"]]["physical_label"]}
            else:
                row=driver.run_benign_drift(task,originals[task["case_id"]],altered,directory/"drift_trials"/task["task_id"])
            row["changed_label_freeze_sha256"]=drift_hash
        journal.append("task_finished",task,result=row);count+=1
        summary=summarize_normal(journal.results,manifest)
        _write_once(directory/f"normal_summary_{len(journal.results):06d}.json",summary)
        print(f"EXP-D {len(journal.results)}/{len(manifest['identity']['tasks'])} {task['mode']} {task['profile']} {task['case_id']} -> {row.get('observed',{}).get('status',row.get('status'))}",flush=True)
        if row.get("cleanup_error"):raise RuntimeError("ambiguous cleanup retained; stop before next task")
    return summarize_normal(journal.results,manifest)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort",type=Path,required=True)
    parser.add_argument("--labels",type=Path,required=True)
    parser.add_argument("--policy",type=Path,default=DEFAULT_POLICY)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--modes",nargs="+",choices=["N0","N1"],default=["N0"])
    parser.add_argument("--profiles",nargs="+",choices=["B4","B5"],default=["B5"])
    parser.add_argument("--repeats",type=int,default=10)
    parser.add_argument("--periods",nargs="+",type=float,default=DEFAULT_PERIODS)
    parser.add_argument("--drift-levels",nargs="+",choices=list(LEVELS),default=list(LEVELS))
    parser.add_argument("--case-id",action="append",default=[])
    parser.add_argument("--asset-family",choices=["robot","agv","process"])
    parser.add_argument("--limit",type=int)
    parser.add_argument("--max-tasks",type=int)
    parser.add_argument("--allow-pilot",action="store_true")
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--collect-drift-labels",action="store_true")
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if args.collect_drift_labels and args.execute:parser.error("freeze drift labels in a separate invocation before admission")
    cohort_path=args.cohort/"cohort_proposal.json" if args.cohort.is_dir() else args.cohort
    settings=isolated_settings()
    candidate,dataset,perturbed=create_normal_manifest(cohort_path,args.labels,args.policy,settings=settings,
        modes=args.modes,repeats=args.repeats,periods=args.periods,levels=args.drift_levels,profiles=args.profiles,
        case_ids=args.case_id,asset_family=args.asset_family,limit=args.limit,allow_pilot=args.allow_pilot)
    manifest=prepare_manifest(args.output_dir/"normal_manifest.json",candidate,resume=args.resume)
    _write_once(args.output_dir/"normal_dataset.json",dataset)
    if perturbed:write_cohort(perturbed,args.output_dir/"drift_cohort")
    if args.collect_drift_labels:
        if perturbed is None:parser.error("N1 must be included to collect drift labels")
        summary=run_shadow_cohort(perturbed,load_json(args.policy),args.output_dir/"drift_independent",safety_url=settings.safety)
        print(json.dumps(summary,ensure_ascii=False));return 0
    if not args.execute:
        print(json.dumps({"manifest_id":manifest["manifest_id"],"planned_attempts":len(manifest["identity"]["tasks"]),
            "unique_safe_cases":manifest["identity"]["unique_safe_cases"],"state":"FROZEN_NOT_EXECUTED"}));return 0
    if os.environ.get("PCAG_REVISION_MODE","").lower() not in {"1","true","yes"}:raise RuntimeError("execution requires PCAG_REVISION_MODE=true")
    with httpx.Client() as client:
        summary=execute_normal(manifest,args.output_dir,NormalGatewayDriver(client,settings,manifest),max_tasks=args.max_tasks)
    print(json.dumps(summary,ensure_ascii=False));return 0


if __name__=="__main__":raise SystemExit(main())
