# PCAG IJAMT Dataset Construction Procedure

Status: detailed benchmark construction procedure for paper reproducibility  
Version: `v1-procedure`

## 1. Why this document exists

The IJAMT paper cannot treat the benchmark as an opaque collection of hand-made
JSON files.

The paper must explain:

- which upstream public sources were used
- which source units were selected
- how source semantics were converted into supervisory PCAG cases
- how unsafe and fault cases were derived
- how labels were assigned and verified

This document is the canonical benchmark-construction procedure for that
explanation.

It should be cited in all later benchmark release notes and used as the source
material for the paper's "Experimental Setup" and "Dataset Construction"
subsections.

## 2. Construction philosophy

The PCAG IJAMT benchmark is **not** a raw robotics or process-learning dataset.

It is a **supervisory execution-assurance benchmark**.

That means each case is built to answer this question:

> If an AI-generated supervisory command were presented to PCAG at runtime,
> should the command be committed, rejected, aborted, or blocked as unsafe?

Because of that, benchmark generation follows a two-stage transformation:

1. upstream source semantics are preserved as provenance
2. those semantics are lowered into the executable or validator-aligned action
   subset of the current PCAG stack

This benchmark therefore combines:

- public source provenance
- frozen normalization rules
- explicit label taxonomy
- mutation rules for unsafe and fault cases

## 3. Canonical construction pipeline

Every case in the frozen benchmark must be produced through the same pipeline.

### Step 1. Source freeze

Before any case is drafted:

- the upstream source must appear in `sources/source_provenance_manifest.*`
- the local acquisition target must be frozen
- the upstream revision or commit must be recorded
- the source family must be allowed by `sources/source_task_selection.md`

No case is allowed to cite a source that has not already passed the freeze
step.

### Step 2. Source unit selection

A case starts from a single source unit.

Depending on the asset family, a source unit may be:

- a task family
- a demonstration episode
- a scene motif
- a process-control rationale
- a disturbance or fault rationale

Each selected source unit must be recorded in case metadata through fields such
as:

- `source_benchmark.source_id`
- `source_benchmark.source_family`
- `source_benchmark.source_unit`
- `source_benchmark.upstream_ref`

### Step 3. Runtime scene/profile standardization

Before supervisory cases are drafted, the selected source family must be mapped
to a frozen benchmark runtime representation.

This requirement is defined in:

- `generation/scene_pack_strategy.md`

Depending on the asset family, the runtime representation is:

- robot -> canonical USD scene
- AGV -> canonical map/config file
- process -> canonical process profile

This step exists because the benchmark must later be executable or at least
runtime-aligned inside the public PCAG stack.

No case should be drafted before its target `scene_id`, `map_id`, or
`profile_id` is frozen.

### Step 4. Supervisory intent abstraction

The raw source unit is then abstracted into a supervisory manufacturing intent.

Examples:

- robot approach or grasp motion -> "pick part from fixture"
- AGV route in warehouse layout -> "move carrier to handoff station"
- TE-style envelope preservation -> "maintain thermal state within safe band"

At this stage the benchmark author should write:

- `scenario_family`
- `operation_context.mission_phase`
- `operation_context.station_or_zone`
- a brief provenance note

This abstraction preserves manufacturing meaning before the case is lowered
into a PCAG-executable form.

### Step 5. Executable action lowering

The supervisory intent must then be lowered into the current PCAG executable
subset defined in `plugin_case_generation_spec.md`.

This step is mandatory for the first frozen benchmark release.

The lowered action must be legal for the current public runtime:

- `robot_arm_01` -> `move_joint`
- `agv_01` -> `move_to`
- `reactor_01` -> `set_heater_output`, `set_cooling_valve`

The benchmark may retain higher-level semantics in metadata, but `action_sequence`
must use the lowered form whenever the case is expected to be directly runnable.

### Step 6. Proof hint preparation

Each case must include enough information for later benchmark tooling to build a
valid proof package at runtime.

This does not mean storing a final proof package in the dataset.

Instead, each case should provide structured hints such as:

- proof freshness expectations
- sensor-hash expectations
- policy version assumptions
- mutation rationale for integrity-layer rejection cases

Typical fields:

- `proof_hints.policy_profile`
- `proof_hints.timestamp_expectation`
- `proof_hints.sensor_hash_strategy`
- `proof_hints.sensor_divergence_strategy`

### Step 7. Label assignment

Every case must define a complete expected outcome triplet:

- `expected_final_status`
- `expected_stop_stage`
- `expected_reason_code`

The benchmark does not accept partial labels.

This is important because the paper needs to evaluate not only whether the case
failed, but also **where** and **why** it failed.

### Step 8. Unsafe mutation or fault injection

Unsafe and fault sets are not authored independently from scratch.

Instead, they are derived from selected nominal families through controlled
mutations.

Unsafe mutations alter the command or projected motion logic while preserving
the same scenario provenance.

Fault injections alter the runtime envelope around the command, such as:

- timestamp freshness
- policy version alignment
- sensor hash consistency
- sensor divergence
- transaction-layer behavior

### Step 9. Quality-gate review

Before a case enters the frozen release, it must pass a manual or scripted
quality gate.

The required checks are:

- provenance exists in the manifest
- source family is permitted by the task-selection document
- `action_sequence` matches the plugin-aware executable subset
- label triplet is internally consistent
- split assignment is correct
- mutation or fault provenance is recorded
- no ad hoc action names were introduced
- the scenario remains meaningful for manufacturing supervision

### Step 10. Frozen packaging

After quality review, cases are packaged into frozen benchmark outputs:

- `nominal_dataset.json`
- `unsafe_dataset.json`
- `fault_dataset.json`
- `dataset_manifest.json`
- `qc_report.md`

No case should be edited in place after the freeze. Revisions should be tracked
as a new dataset version.

## 4. Asset-specific construction rules

The canonical pipeline above applies to all assets, but the lowering rules differ
by plugin family.

## 4.1 Robot dataset construction

### Source regime

Robot nominal cases are derived from selected families in:

- IsaacLab
- MimicGen

### Step A. Choose a robot source unit

Examples:

- a pick-place family
- a stacking family
- an assembly family such as nut assembly or threading

### Step B. Write the supervisory interpretation

The benchmark author must preserve the original industrial interpretation in:

- `scenario_family = robot_manipulation`
- `operation_context.task_family`
- `operation_context.station_id`
- `source_benchmark.source_unit`
- `notes`

Examples of preserved semantics:

- pick from tray
- move to fixture
- insert part
- retreat to safe pose

### Step C. Lower to executable robot form

For the public benchmark release, all robot cases are lowered into:

- `action_type = move_joint`
- `params.target_positions = [...]`

This is required because the current public stack expects Isaac-backed
validation through `target_positions`.

Examples:

- pick motion provenance -> `move_joint` to pick posture
- place motion provenance -> `move_joint` to place posture
- insertion provenance -> `move_joint` to insertion posture
- retreat provenance -> `move_joint` to safe posture

### Step D. Label robot nominal cases

Robot nominal cases should usually be labeled:

- `expected_final_status = COMMITTED`
- `expected_stop_stage = COMMIT_ACK`
- `expected_reason_code = NONE`

### Step E. Derive robot unsafe cases

Robot unsafe mutations should be created from nominal postures by introducing
controlled violations such as:

- joint limit violation
- unsafe target posture
- insertion overshoot
- retreat omission
- workspace boundary violation

These cases normally map to:

- `expected_final_status = UNSAFE`
- `expected_stop_stage = SAFETY_UNSAFE`
- `expected_reason_code = SAFETY_UNSAFE`

### Step F. Derive robot fault cases

Robot fault cases should keep the same supervisory semantics but mutate the
runtime envelope through:

- policy mismatch
- timestamp expired
- sensor hash mismatch
- sensor divergence
- simulation timeout or backend unavailability
- lock denied
- reverify mismatch
- commit timeout or commit failure

## 4.2 AGV dataset construction

### Source regime

AGV cases are grounded in the downloaded warehouse-world reference, but the
cases themselves are repository-curated supervisory scenarios.

### Step A. Choose an AGV source motif

Examples:

- station transfer
- docking approach
- shared-zone entry
- congestion or collision conflict

### Step B. Write the supervisory interpretation

Each case should explicitly preserve:

- route or station meaning
- logistics phase
- whether the case corresponds to transfer, docking, handoff, or zone entry

Examples:

- move carrier to reactor cell
- dock at robot handoff station
- enter shared loading zone

### Step C. Lower to executable AGV form

For the public benchmark release, AGV cases must use:

- `action_type = move_to`
- coordinate-based target parameters

High-level semantics such as `dock` or `move_to_station` should remain in
metadata while the runnable case is lowered to `move_to`.

### Step D. Label AGV nominal cases

AGV nominal cases should typically be:

- in-bounds
- conflict-free
- compatible with the current discrete-event simulator

Expected label:

- `COMMITTED`

### Step E. Derive AGV unsafe cases

Unsafe mutations should include:

- out-of-bounds target
- docking overshoot
- forbidden-zone entry
- congestion or collision route

These should usually end at:

- `SAFETY_UNSAFE`

### Step F. Derive AGV fault cases

Fault families should include:

- stale timestamp
- sensor hash mismatch
- lock denied
- reverify mismatch
- commit timeout
- commit failure

## 4.3 Process-interlock dataset construction

### Source regime

Process cases are grounded in Tennessee Eastman style operating and disturbance
logic, but converted into PLC-governed supervisory cases for the current
reactor-like benchmark asset.

### Step A. Choose a process source motif

Examples:

- normal operating envelope preservation
- manipulated-variable constraint preservation
- disturbance-inspired unsafe thermal state
- interlock-inspired corrective action

### Step B. Write the supervisory interpretation

The benchmark author should preserve:

- process regime
- relevant operating envelope
- intended thermal or cooling adjustment
- interlock rationale

### Step C. Lower to executable process form

For the public benchmark release, the executable process subset is:

- `set_heater_output`
- `set_cooling_valve`

Higher-level semantics such as "hold state" or "enter safe mode" may remain in
metadata but must be lowered to actual heater/cooling commands if the case is
to be run directly.

### Step D. Label process nominal cases

Nominal process cases should:

- preserve temperature and pressure within allowed ranges
- maintain a ruleset-compatible heater/cooling pairing
- remain simulator-safe

Expected label:

- `COMMITTED`

### Step E. Derive process unsafe cases

Unsafe mutations should include:

- excessive heating
- insufficient cooling
- incompatible command combination
- disturbance-inspired unsafe thermal projection

These normally end at:

- `SAFETY_UNSAFE`

### Step F. Derive process fault cases

Fault mutations should include:

- policy mismatch
- timestamp expired
- sensor hash mismatch
- sensor divergence
- reverify mismatch
- commit timeout
- commit failure

## 5. Labeling rules

The benchmark must use the frozen label taxonomy.

### 5.1 Status classes

- `COMMITTED`
- `UNSAFE`
- `REJECTED`
- `ABORTED`
- `ERROR`

### 5.2 Stop-stage classes

Typical examples:

- `COMMIT_ACK`
- `SAFETY_UNSAFE`
- `INTEGRITY_REJECTED`
- `PREPARE_LOCK_DENIED`
- `REVERIFY_FAILED`
- `COMMIT_FAILED`
- `COMMIT_TIMEOUT`

### 5.3 Reason-code rules

Examples:

- `NONE` for successful cases
- `SAFETY_UNSAFE`
- `INTEGRITY_TIMESTAMP_EXPIRED`
- `INTEGRITY_SENSOR_HASH_MISMATCH`
- `LOCK_DENIED`
- `REVERIFY_HASH_MISMATCH`
- `COMMIT_FAILED`
- `COMMIT_TIMEOUT`

The stop stage and reason code must never contradict the final status.

## 6. Mutation families

Unsafe and fault mutation families must be explicit and traceable.

## 6.1 Robot unsafe mutation families

- joint limit violation
- unsafe target posture
- insertion overshoot
- retreat omission
- workspace boundary violation

## 6.2 AGV unsafe mutation families

- out-of-bounds target
- docking overshoot
- forbidden-zone entry
- congestion or collision route

## 6.3 Process unsafe mutation families

- excessive heating
- insufficient cooling
- incompatible heater/cooling combination
- disturbance-inspired unsafe condition

## 6.4 Cross-asset fault families

- policy mismatch
- timestamp expired
- sensor hash mismatch
- sensor divergence
- lock denied
- reverify mismatch
- commit timeout
- commit failure

## 7. Required case metadata

Every frozen case should contain, at minimum:

- stable `case_id`
- `scenario_family`
- `asset_id`
- canonical runtime reference such as `scene_id`, `map_id`, or `profile_id`
- `source_benchmark` block
- `operation_context` block
- executable `action_sequence`
- `proof_hints`
- label block with final status, stop stage, and reason code
- provenance notes for mutations when applicable

## 8. Quality gate checklist

Before a case is frozen, check all items below.

- The source appears in `source_provenance_manifest.*`.
- The family appears in `source_task_selection.md`.
- The runtime reference exists in the frozen scene/profile registry.
- The case uses only frozen action names.
- The case matches the plugin-aware executable subset.
- The label triplet is valid.
- The split assignment is correct.
- The case is meaningful as a manufacturing supervisory command.
- Unsafe and fault cases declare which nominal family they were derived from.

## 9. Frozen release outputs

The first benchmark release should eventually ship with:

- `nominal_dataset.json`
- `unsafe_dataset.json`
- `fault_dataset.json`
- `dataset_manifest.json`
- `qc_report.md`

The `dataset_manifest.json` should include:

- benchmark version
- source manifest version
- task-selection version
- case counts by split
- case counts by asset
- release date

## 10. Paper wording guidance

When this procedure is described in the IJAMT manuscript, the wording should be
careful and explicit.

Recommended phrasing:

- the benchmark is **derived from frozen public benchmark references and
  repository-curated supervisory transformations**
- robot cases are **grounded in IsaacLab and MimicGen task families**
- AGV and process cases are **grounded in public warehouse-world and Tennessee
  Eastman style references, then transformed into supervisory execution cases**
- unsafe and fault cases are **generated through controlled mutations of nominal
  source-aligned cases**

Avoid wording that would imply:

- the benchmark is a raw upstream dataset copied directly without transformation
- the process benchmark is a raw Tennessee Eastman classification dataset
- the public stack already supports richer executable actions than it currently
  does

## 11. Immediate next action

After this procedure is frozen, the next implementation step should be:

1. create `nominal_dataset_first_batch.json`
2. fill it only with cases from selected source families
3. derive unsafe and fault companions through the mutation rules above
