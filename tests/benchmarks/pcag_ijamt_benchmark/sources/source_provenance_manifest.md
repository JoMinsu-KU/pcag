# PCAG IJAMT Source Provenance Manifest

Status: frozen provenance manifest before first benchmark acquisition  
Manifest version: `v1-pre-acquisition`  
Checked on: `2026-03-18`

## 1. Purpose

This manifest is the canonical provenance record for all public or public-grounded
benchmark sources used to build the PCAG IJAMT benchmark.

It exists to answer four questions before any real case drafting begins:

1. Which external or public-grounded sources are allowed?
2. Which exact repository or reference is tied to each source?
3. What local target path should be used when sources are acquired?
4. What is the current acquisition state?

No nominal, unsafe, or fault case should be declared as benchmark-ready unless
its provenance can be traced back to this manifest.

## 2. Acquisition status vocabulary

| status | meaning |
| --- | --- |
| `PENDING_DOWNLOAD` | public source selected, but not yet cloned or downloaded locally |
| `PENDING_REFERENCE_FREEZE` | source is reference-grounded and still needs a final reference note bundle |
| `READY_FOR_EXTRACTION` | locally available and ready for case extraction |
| `READY_FOR_CURATION` | reference frozen and ready for repository-curated supervisory case drafting |

## 3. Selected source records

| source_id | asset family | reference type | verified source | verified ref | local target | current status |
| --- | --- | --- | --- | --- | --- | --- |
| `isaaclab_eval_industrial` | `robot_manipulation` | external benchmark repo | `isaac-sim/IsaacLab` | `f4aa17f87e2e5db5484f0b5974918573e8918ce2` | `external_sources/robot/IsaacLab` | `READY_FOR_EXTRACTION` |
| `mimicgen_assembly` | `robot_manipulation` | external benchmark repo | `NVlabs/mimicgen` | `72bd767c255545f462e7ccfb2731f2e5d4c1d9bb` | `external_sources/robot/mimicgen` | `READY_FOR_EXTRACTION` |
| `warehouse_world_curated` | `agv_logistics` | public world reference + curated supervisory cases | `semitable/robotic-warehouse` | `96fbc64e3eae5fee915e0d390f864fa06ddccd47` | `external_sources/agv/robotic-warehouse-reference` | `READY_FOR_CURATION` |
| `tep_process_curated` | `process_interlock` | public process benchmark reference + curated supervisory cases | `camaramm/tennessee-eastman-challenge` | `a641419365eb292ab4f98888cdcbd7fbfbca890b` | `external_sources/process/tennessee-eastman-reference` | `READY_FOR_CURATION` |

## 4. Detailed records

### 4.1 `isaaclab_eval_industrial`

- Asset family: `robot_manipulation`
- Source type: downloadable external benchmark repository
- Verified upstream URL: `https://github.com/isaac-sim/IsaacLab.git`
- Verified reference: `f4aa17f87e2e5db5484f0b5974918573e8918ce2`
- Verification method: `git ls-remote <repo> HEAD`
- Local acquisition target:
  - `tests/benchmarks/pcag_ijamt_benchmark/external_sources/robot/IsaacLab`
- Planned acquisition mode:
  - clone reference repository
  - extract only the industrial/manufacturing-relevant task families used by the
    benchmark release
- Benchmark role:
  - primary public provenance for robot nominal cases
  - primary source for robot unsafe counterfactual derivation
- Current status: `READY_FOR_EXTRACTION`
- Local acquisition result:
  - shallow clone completed into the frozen local target
  - local `HEAD` verified as `f4aa17f87e2e5db5484f0b5974918573e8918ce2`

### 4.2 `mimicgen_assembly`

- Asset family: `robot_manipulation`
- Source type: downloadable external benchmark repository
- Verified upstream URL: `https://github.com/NVlabs/mimicgen.git`
- Verified reference: `72bd767c255545f462e7ccfb2731f2e5d4c1d9bb`
- Verification method: `git ls-remote <repo> HEAD`
- Local acquisition target:
  - `tests/benchmarks/pcag_ijamt_benchmark/external_sources/robot/mimicgen`
- Planned acquisition mode:
  - clone reference repository
  - extract assembly-oriented task semantics to augment nominal robot diversity
- Benchmark role:
  - secondary public provenance for robot assembly-style nominal cases
  - backup source for additional unsafe mutation families
- Current status: `READY_FOR_EXTRACTION`
- Local acquisition result:
  - shallow clone completed into the frozen local target
  - local `HEAD` verified as `72bd767c255545f462e7ccfb2731f2e5d4c1d9bb`

### 4.3 `warehouse_world_curated`

- Asset family: `agv_logistics`
- Source type: public world reference plus repository-curated supervisory cases
- Verified upstream URL: `https://github.com/semitable/robotic-warehouse.git`
- Verified reference: `96fbc64e3eae5fee915e0d390f864fa06ddccd47`
- Verification method: `git ls-remote <repo> HEAD`
- Local reference target:
  - `tests/benchmarks/pcag_ijamt_benchmark/external_sources/agv/robotic-warehouse-reference`
- Planned acquisition mode:
  - freeze the public warehouse-world reference
  - derive supervisory AGV cases from declared logistics scene assumptions
- Benchmark role:
  - main provenance anchor for AGV nominal, unsafe, and fault case families
- Current status: `READY_FOR_CURATION`
- Local acquisition result:
  - reference repository cloned into the frozen local target
  - local `HEAD` verified as `96fbc64e3eae5fee915e0d390f864fa06ddccd47`
- Note:
  - the benchmark unit is not a raw navigation log; it is a supervisory command
    case grounded in a public warehouse-world reference

### 4.4 `tep_process_curated`

- Asset family: `process_interlock`
- Source type: public process benchmark reference plus repository-curated
  supervisory cases
- Verified upstream URL:
  - `https://github.com/camaramm/tennessee-eastman-challenge.git`
- Verified reference: `a641419365eb292ab4f98888cdcbd7fbfbca890b`
- Verification method: `git ls-remote <repo> HEAD`
- Local reference target:
  - `tests/benchmarks/pcag_ijamt_benchmark/external_sources/process/tennessee-eastman-reference`
- Planned acquisition mode:
  - freeze Tennessee Eastman reference material
  - derive process/interlock supervision motifs for the PLC-backed asset family
- Benchmark role:
  - main provenance anchor for process nominal, unsafe, and fault cases
- Current status: `READY_FOR_CURATION`
- Local acquisition result:
  - reference repository cloned into the frozen local target
  - local `HEAD` verified as `a641419365eb292ab4f98888cdcbd7fbfbca890b`
- Note:
  - the benchmark should not claim to be a raw Tennessee Eastman dataset; it is
    a supervisory benchmark derived from TE-style process-control references

## 5. Immediate acquisition order

1. Extract robot-manipulation task families from `isaaclab_eval_industrial`.
2. Extract assembly-oriented augmentation cases from `mimicgen_assembly`.
3. Write AGV reference notes against `warehouse_world_curated`.
4. Write process reference notes against `tep_process_curated`.

## 6. Gate before nominal case drafting

Nominal case drafting should not start until:

- both robot sources are locally available or explicitly replaced with documented
  alternates,
- AGV reference provenance is frozen,
- process reference provenance is frozen, and
- all sources remain consistent with:
  - `action_vocabulary.md`
  - `label_taxonomy.md`
  - `plugin_case_generation_spec.md`
