# PCAG IJAMT Source Acquisition Plan

Status: execution guide for benchmark source preparation  
Version: `v1-selected`

## 1. Purpose

This file explains how each asset family will obtain its benchmark provenance before real case generation begins.

The authoritative source record for URLs, verified refs, and local target paths
is:

- `source_provenance_manifest.md`
- `source_provenance_manifest.json`

The important rule is that not every asset family needs the same kind of source artifact.

- robot cases should come from downloadable public benchmark sources
- AGV cases should be grounded in public warehouse-world references and then converted into supervisory command cases
- process cases should be grounded in public process-control benchmark references and then converted into supervisory command cases

## 2. Acquisition model by asset family

| asset family | acquisition mode | requires download first? |
| --- | --- | --- |
| `robot_manipulation` | external benchmark acquisition | yes |
| `agv_logistics` | public world reference + repository-curated supervisory cases | partially |
| `process_interlock` | public process benchmark reference + repository-curated supervisory cases | partially |

## 3. Robot acquisition plan

### Selected sources

- `isaaclab_eval_industrial`
- `mimicgen_assembly`

### Required action

- acquire source benchmark tasks or episodes first
- record exact source version or commit
- select nominal episodes for supervisory conversion
- place all local acquisitions under `../external_sources/robot/`

### Why download is required

The robot family is the part of the paper that most clearly benefits from public benchmark provenance.  
It is not enough to invent robot nominal cases by hand if we want the benchmark to look externally grounded.

## 4. AGV acquisition plan

### Selected source

- `warehouse_world_curated`

### Required action

- identify one or two public warehouse-world references
- document the logistics layout assumptions used by our AGV supervision cases
- then create supervisory command cases inside the frozen PCAG schema
- freeze the reference notes under `../external_sources/agv/`

### Why full raw-dataset download is not strictly required

For AGV supervision, the benchmark unit is not a perception frame or a navigation trajectory log by itself.  
What we need is defensible logistics-scene provenance plus a clear mapping into supervisory actions such as:

- `move_to_station`
- `dock`
- `wait`
- `handoff_to_robot`
- `enter_zone`

## 5. Process-interlock acquisition plan

### Selected source

- `tep_process_curated`

### Required action

- document the Tennessee Eastman benchmark references used for process rationale
- extract normal-operation and fault-style supervision motifs
- convert those into supervisory benchmark cases for the PLC-backed asset family
- freeze the reference notes under `../external_sources/process/`

### Why full raw-dataset download is not strictly required

The paper is not evaluating a process-state forecasting model.  
It is evaluating whether PCAG can gate supervisory commands for a process-style asset under nominal, unsafe, and fault conditions.

Therefore, what matters most is:

- clear provenance
- defensible operating constraints
- reproducible mutation and fault rules

## 6. Immediate acquisition order

1. acquire robot sources first
2. document warehouse reference source for AGV
3. document Tennessee Eastman reference source for process/interlock asset
4. only after that begin case drafting

## 7. Minimum acceptance criteria before nominal drafting

Nominal case drafting should not begin until:

- the selected source list is frozen
- robot source provenance is recorded
- AGV reference provenance is recorded
- process benchmark provenance is recorded
- all three asset families are mapped to the frozen action vocabulary
