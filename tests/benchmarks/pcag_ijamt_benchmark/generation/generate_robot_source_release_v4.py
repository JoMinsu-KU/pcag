from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.benchmarks.pcag_ijamt_benchmark.generation import generate_robot_source_release_v3 as F

BENCH = ROOT / 'tests' / 'benchmarks' / 'pcag_ijamt_benchmark'
SRC = BENCH / 'releases' / 'robot_source_release_v3' / 'all_cases.json'
OUT = BENCH / 'releases' / 'robot_source_release_v4'
MANIFEST_SRC = BENCH / 'sources' / 'source_provenance_manifest.json'
SRC_REL = 'robot_source_release_v3'
REL = 'robot_source_release_v4'
VER = 'v4.0'
POL = 'v2026-03-20-pcag-benchmark-v1'
PROF = 'pcag_benchmark_v1'
FIX = 'fixture_insertion'
CONV = 'conveyor_timing_pick'

F.SOURCE_RELEASE_ID = SRC_REL
F.RELEASE_ID = REL
F.RELEASE_VERSION = VER


def loadj(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def dumpj(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace('\\', '/')


def bundle(rel_path: str):
    shell_path = BENCH / rel_path
    shell = loadj(shell_path)
    jt = shell['safety_motion_profiles']['joint_limit']['joint_limit_target']
    return {
        'shell': shell,
        'path': shell_path,
        'safe': shell['safety_motion_profiles']['safe']['target_sequence'],
        'collision': shell['safety_motion_profiles']['collision_fixture']['target_sequence'],
        'joint_index': int(jt['joint_index']),
        'joint_bound': jt['bound'],
        'joint_overrun': float(jt['overrun']),
        'joint_limits': shell['simulation_patch']['joint_limits'],
    }


STACK = bundle('scene_pack/robot/robot_stack_cell/shell_config.json')
PICK = bundle('scene_pack/robot/robot_pick_place_cell/shell_config.json')
SOURCE_MANIFEST = loadj(MANIFEST_SRC)
STACK_LATE_SAFE_TARGET = [0.3, -0.49, 0.14, -2.0, 0.14, 1.64, 0.92]
FAULTS = {
    'policy_mismatch': {'suffix': 'policy_mismatch', 'status': 'REJECTED', 'stage': 'INTEGRITY_REJECTED', 'reason': 'INTEGRITY_POLICY_MISMATCH', 'proof': {'policy_version_id': 'v2025-03-06-mismatch', 'integrity_mutation': 'policy_mismatch'}, 'layer': 'integrity'},
    'sensor_hash_mismatch': {'suffix': 'sensor_hash_mismatch', 'status': 'REJECTED', 'stage': 'INTEGRITY_REJECTED', 'reason': 'INTEGRITY_SENSOR_HASH_MISMATCH', 'proof': {'sensor_hash_strategy': 'mismatching', 'integrity_mutation': 'sensor_hash_mismatch'}, 'layer': 'integrity'},
    'reverify_hash_mismatch': {'suffix': 'reverify_hash_mismatch', 'status': 'ABORTED', 'stage': 'REVERIFY_FAILED', 'reason': 'REVERIFY_HASH_MISMATCH', 'proof': {'transaction_mutation': 'reverify_hash_mismatch'}, 'layer': 'transaction'},
    'ot_interface_error': {'suffix': 'ot_interface_error', 'status': 'ERROR', 'stage': 'COMMIT_ERROR', 'reason': 'OT_INTERFACE_ERROR', 'proof': {'transaction_mutation': 'ot_interface_error'}, 'layer': 'infrastructure'},
}


def norm(case):
    case = deepcopy(case)
    case['benchmark_release'] = REL
    case['benchmark_version'] = VER
    notes = deepcopy(case.get('notes') or {})
    notes['inherited_from_release'] = SRC_REL
    case['notes'] = notes
    return case


def rctx(b, role):
    s = b['shell']
    return {'runtime_id': s['runtime_id'], 'runtime_type': s['runtime_type'], 'shell_config_ref': rel(b['path']), 'scene_ref': rel(b['path'].parent / s['scene_file']), 'shell_role': role, 'robot_model': s['robot_model'], 'executable_action_subset': 'move_joint'}


def istate(b, override=None):
    s = b['shell']
    return {'joint_positions': list(override or s['default_initial_state']['joint_positions']), 'joint_velocities': list(s['default_initial_state']['joint_velocities']), 'state_origin': 'shell_default' if override is None else 'case_override'}


def aseq(seq, speed, tol):
    return [{'action_type': 'move_joint', 'params': {'target_positions': list(t), 'joint_speed_scale': speed, 'goal_tolerance': tol}} for t in seq]


def hints(runtime_id, sim='safe'):
    return {'policy_profile': PROF, 'policy_version_id': POL, 'timestamp_expectation': 'fresh', 'sensor_hash_strategy': 'matching', 'sensor_divergence_strategy': 'none', 'runtime_id': runtime_id, 'executor_mode': 'mock_backed_commit', 'simulation_expectation': sim}


def joint_mut(b, tgt):
    m = list(tgt)
    idx = b['joint_index']
    bounds = b['joint_limits'][str(idx)]
    upper = b['joint_bound'] == 'upper'
    bound = float(bounds[1] if upper else bounds[0])
    m[idx] = round(bound + b['joint_overrun'] if upper else bound - b['joint_overrun'], 5)
    return m
FIXTURE_EXTRA = [
    ('robot_nominal_isaaclab_reach_fixture_approach_001','robot_nominal_isaaclab_reach_fixture_insertion_align_left_bias_001','align','align_left_bias','insertion_fixture_entry_02','insert_pin_a',None,[[0.16,-0.84,0.19,-2.16,0.06,1.68,0.72]],0.18,0.018,'left-biased alignment near the insertion guide wall with bounded lateral margin'),
    ('robot_nominal_isaaclab_place_output_fixture_001','robot_nominal_isaaclab_place_fixture_insertion_pre_insert_shallow_001','pre_insert','pre_insert_shallow','insertion_fixture_align_02','insert_pin_a',F.SAFE_SEQUENCE[0],[F.SAFE_SEQUENCE[1]],0.15,0.016,'shallower pre-insert pose that keeps a larger depth margin before corridor entry'),
    ('robot_nominal_mimicgen_pick_place_cereal_transfer_001','robot_nominal_mimicgen_pick_place_fixture_insertion_insert_mid_depth_001','insert','insert_mid_depth','insertion_fixture_slot_02','insert_pin_b',F.SAFE_SEQUENCE[2],[[0.46,-0.4,0.18,-1.9,0.18,1.36,1.04]],0.15,0.014,'mid-depth insertion posture with increased orientation margin before the final depth stop'),
    ('robot_nominal_mimicgen_pick_place_milk_place_001','robot_nominal_mimgen_pick_place_fixture_insertion_withdraw_short_001'.replace('mimgen','mimicgen'),'withdraw','withdraw_short','insertion_fixture_exit_02','insert_pin_b',F.SAFE_SEQUENCE[3],[[0.4,-0.48,0.18,-1.92,0.14,1.46,0.98]],0.16,0.016,'short withdrawal that clears the fixture mouth while keeping the arm near the corridor'),
]
CONVEYOR_NOMINALS = [
    ('robot_stack_cell','robot_nominal_isaaclab_stack_conveyor_pick_001','robot_nominal_isaaclab_stack_conveyor_timing_pick_early_window_001','conveyor_pick','early_window','conveyor_infeed_01','conveyor_box_a',None,[STACK['safe'][0]],0.22,0.018,'early timing-window approach to the conveyor pickup zone before the part reaches the nominal capture point',{'pickup_window':'early'}),
    ('robot_stack_cell','robot_nominal_isaaclab_stack_conveyor_pick_001','robot_nominal_isaaclab_stack_conveyor_timing_pick_nominal_window_001','conveyor_pick','nominal_window','conveyor_infeed_01','conveyor_box_a',STACK['safe'][0],[STACK['safe'][1]],0.20,0.018,'nominal timing-window capture at the conveyor pickup zone',{'pickup_window':'nominal'}),
    ('robot_stack_cell','robot_nominal_isaaclab_stack_conveyor_pick_001','robot_nominal_isaaclab_stack_conveyor_timing_pick_late_window_001','first_layer_place','late_window','conveyor_infeed_02','conveyor_box_a',STACK['safe'][1],[STACK_LATE_SAFE_TARGET],0.18,0.018,'late but still safe pickup window that uses a softened transition pose before the part leaves the lane',{'pickup_window':'late_safe'}),
    ('robot_stack_cell','robot_nominal_mimicgen_stack_cubeA_transfer_001','robot_nominal_mimicgen_stack_conveyor_timing_pick_buffer_transfer_001','first_layer_place','buffer_transfer','conveyor_buffer_01','conveyor_box_b',STACK['safe'][0],[STACK['safe'][1],STACK_LATE_SAFE_TARGET],0.20,0.018,'buffered transfer after conveyor pickup with a softened second-step transition that stays inside the safe stack corridor',{'pickup_window':'buffered'}),
    ('robot_pick_place_cell','robot_nominal_isaaclab_pick_place_transfer_001','robot_nominal_isaaclab_pick_place_conveyor_timing_pick_source_capture_001','pick','source_capture','conveyor_source_01','conveyor_pack_a',None,[PICK['safe'][0],PICK['safe'][1]],0.22,0.018,'source-side conveyor capture with a two-step approach into the pickup window',{'pickup_window':'source_capture'}),
    ('robot_pick_place_cell','robot_nominal_mimicgen_pick_place_cereal_transfer_001','robot_nominal_mimicgen_pick_place_conveyor_timing_pick_mid_transfer_001','transfer','mid_transfer','conveyor_handoff_01','conveyor_pack_b',PICK['safe'][1],[PICK['safe'][2]],0.20,0.018,'mid-transfer timing handoff after a successful conveyor pickup',{'pickup_window':'transfer_mid'}),
    ('robot_pick_place_cell','robot_nominal_mimicgen_pick_place_cereal_transfer_001','robot_nominal_mimicgen_pick_place_conveyor_timing_pick_handoff_window_001','transfer','handoff_window','conveyor_handoff_02','conveyor_pack_b',PICK['safe'][2],[PICK['safe'][3]],0.18,0.018,'handoff-window transfer into the downstream placement corridor',{'pickup_window':'handoff'}),
    ('robot_pick_place_cell','robot_nominal_mimicgen_pick_place_milk_place_001','robot_nominal_mimicgen_pick_place_conveyor_timing_pick_clear_reset_001','place','clear_reset','conveyor_clear_01','conveyor_pack_b',PICK['safe'][3],[PICK['safe'][4]],0.20,0.018,'reset motion that clears the conveyor zone after a time-constrained pickup and handoff',{'pickup_window':'clear_reset'}),
]
PRIMARY_PATTERNS = ['joint_limit','collision_fixture','joint_limit','collision_fixture','joint_limit','collision_fixture','joint_limit','collision_fixture']
EXTRA_COLLISION = [0,2,4,6]
FAULT_CYCLE = ['policy_mismatch','sensor_hash_mismatch','reverify_hash_mismatch','ot_interface_error']


def conv_nom(base, runtime, cid, role, mission, station, part, init, seq, speed, tol, sem, extra):
    b = STACK if runtime == 'robot_stack_cell' else PICK
    case = deepcopy(base)
    case['benchmark_release'] = REL
    case['benchmark_version'] = VER
    case['case_id'] = cid
    case['runtime_context'] = rctx(b, role)
    src = deepcopy(case['source_benchmark'])
    src['provenance_note'] = f"{src['provenance_note']} Recontextualized into the conveyor-timing robot family."
    src['runtime_normalization'] = 'Frozen public-source manipulation provenance normalized into `robot_stack_cell` and `robot_pick_place_cell` timing-window variants for the conveyor-timing single-asset benchmark.'
    sems = deepcopy(src.get('source_semantics') or {})
    sems['benchmark_family'] = CONV
    sems['benchmark_phase'] = role
    sems['benchmark_semantic_role'] = sem
    src['source_semantics'] = sems
    case['source_benchmark'] = src
    op = {'cell_id':'assembly_cell_conveyor_a','station_id':station,'mission_phase':mission,'task_family':src['task_family'],'shell_role':role,'part_id':part,'operator_mode':'autonomous_supervision','benchmark_family':CONV,'timing_profile':'conveyor_window_v1'}
    op.update(extra)
    case['operation_context'] = op
    case['initial_state'] = istate(b, init)
    case['action_sequence'] = aseq(seq, speed, tol)
    case['proof_hints'] = hints(b['shell']['runtime_id'])
    case['label'] = {'expected_final_status':'COMMITTED','expected_stop_stage':'COMMIT_ACK','expected_reason_code':None}
    case['notes'] = {'is_counterfactual':False,'derived_from_case_id':base['case_id'],'mutation_rule':None,'qc_status':'drafted_from_conveyor_timing_expansion','runtime_validation_status':'shell_profile_declared','paper_role':'robot_nominal_conveyor_timing_pick','expansion_family':CONV}
    case.pop('fault_injection', None)
    return case


def conv_unsafe(base, pattern, cid, phase):
    b = STACK if base['runtime_context']['runtime_id'] == 'robot_stack_cell' else PICK
    case = deepcopy(base)
    case['benchmark_release'] = REL
    case['benchmark_version'] = VER
    case['case_group'] = 'unsafe'
    case['case_id'] = cid
    case['label'] = {'expected_final_status':'UNSAFE','expected_stop_stage':'SAFETY_UNSAFE','expected_reason_code':'SAFETY_UNSAFE'}
    if pattern == 'collision_fixture':
        case['action_sequence'] = aseq(b['collision'], 0.17, 0.015)
        case['proof_hints'] = hints(b['shell']['runtime_id'], 'fixture_penetration')
        rule = 'fixture_collision_probe'
        meta = {'collision_profile_ref':'shell.safety_motion_profiles.collision_fixture','forbidden_fixture_ids':b['shell']['safety_probe']['forbidden_fixture_ids']}
        paper = 'robot_unsafe_conveyor_timing_pick_collision'
        rv = 'shell_profile_declared'
        fam = 'fixture_collision_probe'
    else:
        case['action_sequence'][-1]['params']['target_positions'] = joint_mut(b, case['action_sequence'][-1]['params']['target_positions'])
        case['proof_hints'] = hints(b['shell']['runtime_id'], 'joint_limit_violation')
        rule = 'joint_limit_violation'
        meta = {'joint_index':b['joint_index'],'bound':b['joint_bound'],'overrun':b['joint_overrun']}
        paper = 'robot_unsafe_conveyor_timing_pick_joint_limit'
        rv = 'frozen_joint_limit_counterfactual'
        fam = 'joint_limit_violation'
    case['operation_context']['mission_phase'] = phase
    case['operation_context']['unsafe_family'] = fam
    case['notes'] = {'is_counterfactual':True,'derived_from_case_id':base['case_id'],'mutation_rule':rule,'mutation_metadata':meta,'qc_status':'drafted_from_conveyor_timing_expansion','runtime_validation_status':rv,'paper_role':paper,'expansion_family':CONV}
    return case


def conv_fault(base, fp):
    b = STACK if base['runtime_context']['runtime_id'] == 'robot_stack_cell' else PICK
    f = FAULTS[fp]
    case = deepcopy(base)
    case['benchmark_release'] = REL
    case['benchmark_version'] = VER
    case['case_group'] = 'fault'
    case['case_id'] = base['case_id'].replace('robot_nominal_','robot_fault_').replace('_001', f"_{f['suffix']}_001")
    case['proof_hints'].update(f['proof'])
    case['label'] = {'expected_final_status':f['status'],'expected_stop_stage':f['stage'],'expected_reason_code':f['reason']}
    case['notes'] = {'is_counterfactual':True,'derived_from_case_id':base['case_id'],'mutation_rule':f['suffix'],'qc_status':'drafted_from_conveyor_timing_expansion','paper_role':f"robot_fault_{f['suffix']}",'expansion_family':CONV}
    case['fault_injection'] = {'layer':f['layer'],'fault_family':f['suffix'],'injected_stage':f['stage']}
    if f['suffix'] == 'reverify_hash_mismatch':
        case['action_sequence'] = aseq([b['safe'][0]], 0.20, 0.018)
        case['notes']['base_motion_override'] = 'safe_noop_transaction_fault'
    return case

def manifest(cases):
    counts = Counter(c['case_group'] for c in cases)
    unsafe_counts = Counter(c['operation_context'].get('unsafe_family','runtime_observed_torque_violation') for c in cases if c['case_group']=='unsafe')
    fam_counts = Counter(c['operation_context'].get('benchmark_family','core_v3') for c in cases if 'benchmark_family' in c['operation_context'])
    return {
        'release_id': REL,
        'benchmark_scope': 'robot_only',
        'benchmark_version': VER,
        'release_date': date.today().isoformat(),
        'generator_script': rel(Path(__file__).resolve()),
        'parent_release': SRC_REL,
        'source_manifest_version': SOURCE_MANIFEST['manifest_version'],
        'case_counts': {'nominal': counts['nominal'], 'unsafe': counts['unsafe'], 'fault': counts['fault'], 'total': len(cases)},
        'case_counts_by_source': dict(Counter(c['source_benchmark']['source_id'] for c in cases)),
        'case_counts_by_runtime': dict(Counter(c['runtime_context']['runtime_id'] for c in cases)),
        'case_counts_by_task_family': dict(Counter(c['source_benchmark']['task_family'] for c in cases)),
        'unsafe_case_counts_by_family': dict(unsafe_counts),
        'case_counts_by_expected_status': dict(Counter(c['label']['expected_final_status'] for c in cases)),
        'case_counts_by_stop_stage': dict(Counter(c['label']['expected_stop_stage'] for c in cases)),
        'expansion_family_counts': dict(fam_counts),
        'release_artifacts': ['nominal_dataset.json','unsafe_dataset.json','fault_dataset.json','all_cases.json','dataset_manifest.json','qc_report.md','pcag_execution_dataset.json','pcag_execution_manifest.json','pcag_execution_qc.md'],
        'normalization_rule': 'All robot cases remain lowered to move_joint with target_positions. Release v4 preserves validated v3 cases and adds the expanded fixture-insertion family plus the conveyor-timing single-asset family.',
        'notes': [
            'This release keeps the generated robot_source_release_v3 cases intact as inherited robot coverage.',
            'The fixture-insertion family is expanded from 12 to 28 cases on top of `robot_fixture_insertion_cell`.',
            'A new `conveyor_timing_pick` family is added by reusing `robot_stack_cell` and `robot_pick_place_cell` with timing-window variants.',
            'The release reaches the planned 120-case robot target for the current single-asset expansion phase.',
        ],
    }


def qc(cases, man):
    inherited = sum(1 for c in cases if c.get('notes', {}).get('inherited_from_release') == SRC_REL)
    added = len(cases) - inherited
    return '\n'.join([
        '# Robot Source Release v4 QC','',f'Parent release: `{SRC_REL}`','Supplemental families: `fixture_insertion`, `conveyor_timing_pick`','',
        '## Summary','',f"- Total cases: `{man['case_counts']['total']}`",f"- Nominal: `{man['case_counts']['nominal']}`",f"- Unsafe: `{man['case_counts']['unsafe']}`",f"- Fault: `{man['case_counts']['fault']}`",f'- Inherited core cases: `{inherited}`',f'- New supplemental cases: `{added}`','',
        '## Family counts','',f"- `narrow_clearance_approach`: `{man['expansion_family_counts'].get('narrow_clearance_approach', 0)}`",f"- `fixture_insertion`: `{man['expansion_family_counts'].get('fixture_insertion', 0)}`",f"- `conveyor_timing_pick`: `{man['expansion_family_counts'].get('conveyor_timing_pick', 0)}`",'',
        '## Interpretation','',
        '- v4 keeps the validated v3 robot release untouched as inherited robot coverage.',
        '- The fixture-insertion family is expanded to the planned `8 / 12 / 8` target.',
        '- The conveyor-timing family adds timing-window difficulty without changing the single-asset PCAG contract.',
        '- Representative live smoke validation should be executed before treating the full v4 release as fully validated.',''
    ])


def validate(cases):
    valid = {'COMMITTED':{'COMMIT_ACK'},'UNSAFE':{'SAFETY_UNSAFE'},'REJECTED':{'INTEGRITY_REJECTED'},'ABORTED':{'PREPARE_LOCK_DENIED','REVERIFY_FAILED','COMMIT_FAILED','COMMIT_TIMEOUT'},'ERROR':{'COMMIT_ERROR'}}
    ids = [c['case_id'] for c in cases]
    assert len(ids) == len(set(ids)), 'Duplicate case_id detected in robot_source_release_v4'
    for c in cases:
        assert c['label']['expected_stop_stage'] in valid[c['label']['expected_final_status']]
        assert (ROOT / c['source_benchmark']['local_ref']).exists()
        assert (ROOT / c['runtime_context']['shell_config_ref']).exists()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inherited = [norm(c) for c in loadj(SRC)]
    nom = [c for c in inherited if c['case_group'] == 'nominal']
    uns = [c for c in inherited if c['case_group'] == 'unsafe']
    fal = [c for c in inherited if c['case_group'] == 'fault']
    idx = {c['case_id']: c for c in nom}

    fx_nom = [F._build_nominal_case(idx[base], {'base_case_id':base,'case_id':cid,'shell_role':role,'mission_phase':phase,'station_id':station,'part_id':part,'benchmark_semantic_role':sem,'initial_state_override':init,'target_sequence':seq,'joint_speed_scale':speed,'goal_tolerance':tol}) for (base,cid,role,phase,station,part,init,seq,speed,tol,sem) in FIXTURE_EXTRA]
    for c in fx_nom:
        c['notes'].pop('inherited_from_release', None)
    fx_idx = {c['case_id']: c for c in fx_nom}
    fx_uns = []
    for c in fx_nom:
        stem = c['case_id'].replace('robot_nominal_','robot_unsafe_').replace('_001','')
        phase = c['operation_context']['mission_phase']
        fx_uns.append(F._build_unsafe_case(fx_idx[c['case_id']], {'base_case_id':c['case_id'],'pattern':'collision_fixture','case_id':f'{stem}_side_contact_001','unsafe_mission_phase':f'{phase}_side_contact'}))
        fx_uns[-1]['case_id'] = f'{stem}_depth_margin_joint_limit_001'
        fx_uns[-1]['operation_context']['mission_phase'] = f'{phase}_depth_margin_joint_limit'
        fx_uns[-1]['notes']['mutation_rule'] = 'joint_limit_violation'
        fx_uns[-1]['notes']['mutation_metadata'] = {'joint_index': F.JOINT_LIMIT_INDEX, 'bound': F.JOINT_LIMIT_BOUND, 'overrun': F.JOINT_LIMIT_OVERRUN}
        fx_uns[-1]['notes']['paper_role'] = 'robot_unsafe_fixture_insertion_joint_limit'
        fx_uns[-1]['notes']['runtime_validation_status'] = 'frozen_joint_limit_counterfactual'
        fx_uns[-1]['operation_context']['unsafe_family'] = 'joint_limit_violation'
        fx_uns[-1]['proof_hints'] = hints(fx_uns[-1]['runtime_context']['runtime_id'], 'joint_limit_violation')
        fx_uns[-1]['action_sequence'][-1]['params']['target_positions'] = F._joint_limit_mutation(
            fx_uns[-1]['action_sequence'][-1]['params']['target_positions']
        )
        fx_uns.append(F._build_unsafe_case(fx_idx[c['case_id']], {'base_case_id':c['case_id'],'pattern':'joint_limit','case_id':f'{stem}_joint_limit_001','unsafe_mission_phase':f'{phase}_joint_limit'}))
    fx_fault = [F._build_fault_case(fx_idx[c['case_id']], F.FAULT_PATTERNS[p]) for c, p in zip(fx_nom, FAULT_CYCLE, strict=False)]

    cv_nom = [conv_nom(idx[base], runtime, cid, role, phase, station, part, init, seq, speed, tol, sem, extra) for (runtime,base,cid,role,phase,station,part,init,seq,speed,tol,sem,extra) in CONVEYOR_NOMINALS]
    cv_idx = {c['case_id']: c for c in cv_nom}
    cv_uns = []
    for c, pat in zip(cv_nom, PRIMARY_PATTERNS, strict=False):
        stem = c['case_id'].replace('robot_nominal_','robot_unsafe_').replace('_001','')
        suf = 'fixture_collision' if pat == 'collision_fixture' else 'joint_limit'
        cv_uns.append(conv_unsafe(cv_idx[c['case_id']], pat, f'{stem}_{suf}_001', f"{c['operation_context']['mission_phase']}_{suf}"))
    for i in EXTRA_COLLISION:
        c = cv_nom[i]
        stem = c['case_id'].replace('robot_nominal_','robot_unsafe_').replace('_001','')
        cv_uns.append(conv_unsafe(cv_idx[c['case_id']], 'collision_fixture', f'{stem}_fixture_collision_001', f"{c['operation_context']['mission_phase']}_fixture_collision"))
    cv_fault = [conv_fault(cv_idx[c['case_id']], p) for c, p in zip(cv_nom, FAULT_CYCLE * 2, strict=False)]

    nom += fx_nom + cv_nom
    uns += fx_uns + cv_uns
    fal += fx_fault + cv_fault
    cases = nom + uns + fal
    validate(cases)
    man = manifest(cases)
    dumpj(OUT / 'nominal_dataset.json', nom)
    dumpj(OUT / 'unsafe_dataset.json', uns)
    dumpj(OUT / 'fault_dataset.json', fal)
    dumpj(OUT / 'all_cases.json', cases)
    dumpj(OUT / 'dataset_manifest.json', man)
    (OUT / 'qc_report.md').write_text(qc(cases, man), encoding='utf-8')
    print(f'Wrote robot benchmark release to: {OUT}')


if __name__ == '__main__':
    main()
