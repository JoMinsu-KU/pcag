# PCAG IJAMT Benchmark Source Shortlist

Status: selected source plan for benchmark generation  
Version: `v1-selected`

## 1. Purpose

This file narrows the candidate public benchmark sources down to a practical shortlist for the first IJAMT benchmark release.

The shortlist is not meant to be an exhaustive survey.  
It is the operational source-selection reference used to generate supervisory command cases for PCAG.

## 2. Selection rules

Each source in this shortlist was chosen because it helps satisfy at least one of the following needs:

- manufacturing or assembly context
- trajectory or demonstration provenance
- compatibility with robot-centric supervisory command abstraction
- suitability for nominal-to-unsafe counterfactual mutation
- compatibility with the existing Isaac-backed or simulation-backed evaluation story

## 3. Selected source summary

| source_id | priority | main use | primary asset family | role in release |
| --- | --- | --- | --- | --- |
| `isaaclab_eval_industrial` | high | robot manipulation nominal cases | `robot_manipulation` | main source |
| `mimicgen_assembly` | high | robot assembly variation and nominal diversity | `robot_manipulation` | secondary source |
| `warehouse_world_curated` | high | AGV supervisory logistics cases grounded in public warehouse-world references | `agv_logistics` | main source |
| `tep_process_curated` | high | PLC-backed process and interlock cases grounded in Tennessee Eastman references | `process_interlock` | main source |
| `robomimic_assembly` | medium | additional assembly case diversity | `robot_manipulation` | optional expansion |
| `rlbench_reference` | low | appendix/generalization only | `robot_manipulation` | optional appendix |

## 4. Selected source definitions

## 4.1 `isaaclab_eval_industrial`

### Why this source is selected

- strongest alignment with an Isaac-backed robot validation story
- easiest path to explain nominal manufacturing or manipulation episodes in paper form
- naturally supports conversion into `pick`, `place`, `move_to_fixture`, `insert_part`, and `move_joint`

### Intended use

- robot nominal set
- robot unsafe counterfactuals derived from nominal cases

### Expected benchmark contribution

- 20-40 nominal robot cases for the first release
- 20-40 unsafe robot mutations

### Mapping examples

| raw task intent | normalized action |
| --- | --- |
| approach and grasp a part | `pick` |
| move to assembly fixture | `move_to_fixture` |
| insertion motion | `insert_part` |
| posture change or joint target | `move_joint` |

## 4.2 `mimicgen_assembly`

### Why this source is selected

- useful for adding variation without inventing arbitrary nominal cases
- supports assembly-flavored semantics that fit IJAMT better than generic manipulation only

### Intended use

- diversify robot manipulation nominal cases
- generate additional counterfactual unsafe cases from realistic assembly motion intent

### Expected benchmark contribution

- 10-20 additional nominal robot cases
- 10-20 unsafe robot mutations

### Mapping examples

| raw task intent | normalized action |
| --- | --- |
| align part with slot | `move_to_fixture` |
| place component into fixture | `insert_part` |
| move object between stations | `place` |

## 4.3 `warehouse_world_curated`

### Why this source is selected

- public benchmark support is weaker for AGV supervisory execution than for robot manipulation
- warehouse and logistics environments are still preferable to fully ad hoc AGV cases
- the repository already contains meaningful AGV live and hybrid semantics that can be expressed as supervisory commands

### Intended use

- AGV nominal, unsafe, and fault cases

### Data provenance rule

This source is repository-curated, but it must be grounded in public warehouse-world references.

To keep it academically defensible:

- each scenario must be tied to a documented logistics supervision rationale
- each case must be generated from a declared rule, constraint, or live scenario family
- no ad hoc one-off paper-only cases should be added without provenance notes

### Expected benchmark contribution

- 30-40 AGV cases across nominal/unsafe/fault

### Mapping examples

| scenario type | normalized action |
| --- | --- |
| move material carrier to cell | `move_to_station` |
| final station approach | `dock` |
| enter shared work zone | `enter_zone` |

## 4.4 `tep_process_curated`

### Why this source is selected

- the Tennessee Eastman family is one of the most recognizable public process-control benchmark traditions
- it gives the process asset family external provenance instead of relying only on repository-internal scenarios
- PCAG does not need raw process-learning trajectories, but it does need defensible process supervision semantics

### Intended use

- PLC-backed process/interlock nominal, unsafe, and fault cases

### Data provenance rule

This source is repository-curated, but its operating envelope, fault conditions, and process supervision rationale must be tied back to Tennessee Eastman benchmark references.

To keep it academically defensible:

- each case must declare whether it came from normal operation, constraint preservation, or fault-inspired process supervision
- each unsafe or fault case must reference a process constraint, interlock rule, or benchmark-style disturbance rationale
- the benchmark should not claim to be a raw Tennessee Eastman dataset; it is a supervisory benchmark derived from TE-style process-control references

### Expected benchmark contribution

- 30-40 process/interlock cases across nominal/unsafe/fault

### Mapping examples

| scenario type | normalized action |
| --- | --- |
| increase thermal output in allowed envelope | `set_heater_output` |
| preserve a stable operating condition | `hold_state` |
| cooling response adjustment | `open_cooling_valve` |
| process mode transition | `set_process_mode` |

## 4.5 `robomimic_assembly`

### Why this source remains optional

- useful if additional nominal assembly diversity is needed
- less central than the Isaac-backed path for the current repository story

### Intended use

- expansion only
- not required for the first benchmark freeze

## 4.6 `rlbench_reference`

### Why this source is low priority

- useful for appendix-style generalization
- weaker manufacturing framing than the main shortlist

### Intended use

- optional appendix
- not part of the first benchmark release

## 5. First release source decision

The first frozen benchmark release should use the following source mix.

### Main release sources

- `isaaclab_eval_industrial`
- `mimicgen_assembly`
- `warehouse_world_curated`
- `tep_process_curated`

### Deferred sources

- `robomimic_assembly`
- `rlbench_reference`

## 6. Asset coverage plan

| asset family | primary source | backup source |
| --- | --- | --- |
| `robot_manipulation` | `isaaclab_eval_industrial` | `mimicgen_assembly` |
| `agv_logistics` | `warehouse_world_curated` | repository scenario expansion |
| `process_interlock` | `tep_process_curated` | repository scenario expansion |

## 7. Acceptance rule for adding a new source

A new source can be added only if:

- it adds non-redundant manufacturing semantics, or
- it improves diversity for a currently weak asset family, and
- its trajectory semantics can be normalized into the frozen action vocabulary without creating ad hoc actions

## 8. Immediate next step

The first actual generation pass should proceed with this order:

1. `isaaclab_eval_industrial` robot nominal extraction
2. `warehouse_world_curated` AGV nominal drafting
3. `tep_process_curated` process/interlock nominal drafting
4. `mimicgen_assembly` robot nominal augmentation
