# PCAG IJAMT Source Task Selection

Status: frozen task-family selection notes for benchmark construction  
Version: `v1-selection`

## 1. Purpose

This document records which downloaded source families are allowed to feed the
first PCAG IJAMT benchmark release, and why.

The benchmark is not intended to reproduce each upstream source verbatim.
Instead, the benchmark reuses upstream task families as provenance anchors for
PCAG-specific supervisory command cases. Because of that, source selection must
be explicit, reproducible, and narrow enough to avoid ad hoc case authoring.

This file should be read together with:

- `sources/source_provenance_manifest.*`
- `plugin_case_generation_spec.md`
- `action_vocabulary.md`
- `generation/dataset_construction_procedure.md`

## 2. Selection philosophy

Task families are selected only when they satisfy all of the following:

- they preserve a manufacturing, assembly, logistics, or process-control
  interpretation that can be defended in an IJAMT submission
- they can be normalized into the frozen PCAG supervisory vocabulary without
  inventing paper-only action names
- they remain compatible with the current public PCAG runtime subset
- they support nominal cases and meaningful unsafe or fault-derived mutations

Task families are excluded or deferred when they are:

- too household-oriented or weakly connected to manufacturing
- difficult to lower into the current PCAG executable subset
- likely to require custom semantics that are not yet frozen in the benchmark

## 3. Robot source selection

Robot cases are the most provenance-sensitive asset family in the current
benchmark because their nominal cases should be grounded in actual public task
families rather than only repository-authored scenarios.

### 3.1 IsaacLab task families

The downloaded IsaacLab tree currently exposes manipulation families including:

- `reach`
- `lift`
- `pick_place`
- `place`
- `stack`
- `deploy`
- `cabinet`
- `inhand`

For the first benchmark release, the following task families are selected.

#### Selected

##### `reach`

Why it is included:

- clean supervisory interpretation as target approach or pre-grasp motion
- easy lowering into `move_joint` target postures
- useful as nominal setup stage or safe target posture baseline

PCAG benchmark role:

- nominal approach cases
- safe target posture reference
- unsafe mutation seed when target postures are moved outside workspace or joint
  limits

##### `lift`

Why it is included:

- naturally corresponds to part pickup or post-grasp elevation
- easy to interpret in manufacturing handling and assembly preparation
- useful for nominal and unsafe posture derivation

PCAG benchmark role:

- nominal robot transport and elevation phases
- unsafe mutations such as excessive target displacement or unstable posture

##### `pick_place`

Why it is included:

- strongest direct connection to manufacturing part transfer semantics
- easy to map to PCAG supervisory provenance such as pick, transfer, place, and
  handoff phases
- easy to lower into `move_joint` executable cases while preserving high-level
  intent in metadata

PCAG benchmark role:

- primary nominal family for robot motion intent
- base family for unsafe mutations such as target overshoot or forbidden target
  posture

##### `place`

Why it is included:

- captures final alignment and deposition semantics
- useful for station-level or fixture-level target posture cases
- supports manufacturing-cell interpretation better than generic manipulation
  only

PCAG benchmark role:

- nominal station arrival and placement phases
- precise posture safety cases

##### `stack`

Why it is included:

- strong assembly-style semantics
- useful for multi-step target positioning and constrained placement
- can be reinterpreted as part-on-part or part-on-fixture placement

PCAG benchmark role:

- nominal assembly positioning
- unsafe counterfactuals involving alignment error or posture violation

##### `deploy/gear_assembly`

Why it is included:

- closest family to explicit manufacturing assembly semantics in the IsaacLab
  tree
- high value for IJAMT framing because it resembles industrial assembly rather
  than household manipulation

PCAG benchmark role:

- assembly-oriented nominal cases
- insertion-like or fixture-approach provenance notes

#### Deferred or excluded

##### `cabinet`

Reason:

- useful for contact-rich manipulation research, but weaker manufacturing
  framing for the first benchmark freeze
- harder to explain as a manufacturing cell supervision scenario than
  pick/place/assembly families

Decision:

- defer to future expansion or appendix only

##### `inhand`

Reason:

- dexterous manipulation semantics are too far from the current public PCAG
  action subset
- likely to produce benchmark cases that require custom lowering rules

Decision:

- exclude from release `v1`

##### `dexsuite`

Reason:

- dexterous manipulation emphasis is outside the current benchmark narrative
- would expand the benchmark into a different robotics regime

Decision:

- exclude from release `v1`

### 3.2 MimicGen task families

The downloaded MimicGen tree currently exposes:

- `nut_assembly`
- `threading`
- `three_piece_assembly`
- `pick_place`
- `stack`
- `coffee`
- `hammer_cleanup`
- `mug_cleanup`
- `kitchen`

For the first benchmark release, the following task families are selected.

#### Selected

##### `nut_assembly`

Why it is included:

- explicit assembly semantics
- easy to use as provenance for part alignment, insertion, and tightening-style
  motions
- highly aligned with IJAMT manufacturing expectations

##### `threading`

Why it is included:

- assembly insertion and alignment semantics
- useful for fine-positioning or fixture-entry provenance
- supports unsafe mutation around precise posture targets

##### `three_piece_assembly`

Why it is included:

- captures multi-step assembly structure
- useful for stage-specific supervisory case construction
- supports richer provenance while still lowering to `move_joint`

##### `pick_place`

Why it is included:

- provides additional nominal diversity when IsaacLab task families are too
  narrow
- easy to normalize into the same supervisory vocabulary

##### `stack`

Why it is included:

- useful assembly-like part positioning family
- helpful for safe/unsafe placement posture mutations

#### Excluded or deferred

##### `coffee`

Reason:

- household-oriented semantics are not strong enough for manufacturing framing

Decision:

- exclude from release `v1`

##### `hammer_cleanup`

Reason:

- cleanup semantics are weakly connected to the current manufacturing-cell
  storyline

Decision:

- exclude from release `v1`

##### `mug_cleanup`

Reason:

- not a good fit for industrial assembly or material-transfer framing

Decision:

- exclude from release `v1`

##### `kitchen`

Reason:

- too broad and household-centered for the first frozen release

Decision:

- defer indefinitely unless an appendix needs out-of-domain generalization

## 4. AGV source selection

The AGV benchmark uses the downloaded `robotic-warehouse-reference` source as a
public logistics-world anchor rather than as a raw labeled command dataset.

### Selected scenario motifs

The following public-reference motifs are selected for the first release.

#### Station transfer

- AGV moves from a current location toward a named production or handoff
  station
- lowered into `move_to` with station coordinates

#### Docking approach

- AGV performs final approach to a docking pose or pickup/dropoff point
- lowered into `move_to` with docking coordinates

#### Shared-zone entry

- AGV enters a constrained zone shared with another asset or workflow
- lowered into `move_to` with zone entry coordinates and context metadata

#### Congestion or collision conflict

- route or target placement is safe or unsafe depending on occupancy assumptions
- used for unsafe and conflict-derived mutations

#### Wait-or-reroute context

- provenance retains waiting or rerouting semantics
- executable release `v1` still lowers the case into `move_to`

### Deferred motifs

The following are deferred because they would require richer executable support
than the current public AGV path provides:

- explicit queue-management actions
- scheduler-level dispatch actions
- fleet-level cooperative planning actions

These may still appear later as provenance notes, but not as primary executable
action types in release `v1`.

## 5. Process source selection

The process-interlock benchmark uses the downloaded Tennessee Eastman reference
tree as a public process-control anchor.

The benchmark does not claim to reproduce raw Tennessee Eastman time-series
classification or fault-diagnosis tasks. Instead, it derives supervisory
interlock and envelope-preservation cases from TE-style operating logic and
fault rationale.

### Selected process motifs

#### Normal operating envelope preservation

- nominal cases that preserve process variables inside safe operating ranges
- lowered into executable commands such as `set_heater_output` and
  `set_cooling_valve`

#### Manipulated-variable constraint compliance

- cases centered on heater and cooling settings that remain within safe
  envelopes
- useful for direct `COMMITTED` nominal cases

#### Disturbance-inspired supervision

- cases derived from disturbance or fault rationale but framed as supervisory
  command decisions
- useful for unsafe and fault-seeded process cases

#### Interlock-compatible recovery logic

- cases that emphasize cooling, suppression, or safe-state command selection
- useful for unsafe prevention and recovery framing

### Supporting evidence in the downloaded source

The TE reference tree already contains:

- process tables under `tables/`
- disturbance/control reference material
- multiple control-strategy folders and archives

This is sufficient for benchmark provenance, provided that each derived case
explicitly records the supervisory interpretation in metadata.

### Deferred motifs

The following are deferred because they are too close to controller-design
research rather than execution-assurance benchmarking:

- raw controller tuning comparisons
- long-horizon optimal control studies
- direct fault-diagnosis classification tasks

## 6. First frozen release decision

The first frozen release should only generate nominal cases from the following
selected families:

### Robot

- IsaacLab: `reach`, `lift`, `pick_place`, `place`, `stack`, `deploy/gear_assembly`
- MimicGen: `nut_assembly`, `threading`, `three_piece_assembly`, `pick_place`,
  `stack`

### AGV

- station transfer
- docking approach
- shared-zone entry

### Process

- normal operating envelope preservation
- manipulated-variable constraint compliance
- disturbance-inspired supervision

Unsafe and fault cases should be derived from these selected nominal families
instead of being authored independently.

## 7. Usage rule

If a future benchmark case cites a task family or scenario motif that is not
listed as selected here, it should not enter the frozen release until this file
is updated first.
