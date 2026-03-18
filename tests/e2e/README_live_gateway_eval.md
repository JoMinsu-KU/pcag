# Live Gateway E2E Evaluation

This suite exercises the real running PCAG stack through a single public entry
point: every case is submitted only to the Gateway, and the rest of the
pipeline is executed by the live services behind it.

## What This Suite Verifies

The runner validates the following interfaces before execution:

- `Gateway`: `http://127.0.0.1:8000/v1/control-requests`
- `Safety Cluster`: `http://127.0.0.1:8001/v1/validate`
- `Policy Store`: `http://127.0.0.1:8002/v1/policies/active`
- `Sensor Gateway`: `http://127.0.0.1:8003/v1/assets/{asset_id}/snapshots/latest`
- `OT Interface`: `http://127.0.0.1:8004/v1/prepare`, `/commit`, `/abort`
- `Evidence Ledger`: `http://127.0.0.1:8005/v1/transactions/{transaction_id}`
- `Policy Admin`: `http://127.0.0.1:8006/openapi.json`
- `PLC Adapter`: `http://127.0.0.1:8007/v1/health`

The suite defaults to `127.0.0.1` instead of `localhost`. On some Windows
setups, `localhost` resolves to IPv6 (`::1`) first, which can introduce
avoidable retry delay when the services are listening on IPv4 only.

## Single-Entry Dataset Design

Each case in the dataset declares only the semantic intent of the scenario:

- `asset_id`
- `proof.action_sequence_ref`
- optional high-level overrides such as `timestamp_offset_ms`,
  `policy_version_override`, or `sensor_snapshot_hash_override`
- the expected Gateway result and evidence expectations

The runner automatically fills the live proof package with:

- active `policy_version_id`
- latest `sensor_snapshot_hash`
- latest `sensor_reliability_index`
- current `timestamp_ms`

That design keeps the dataset stable while still validating real live state.

## Dataset And Support Files

- Dataset: [`live_gateway_eval_dataset.json`](./live_gateway_eval_dataset.json)
- Runner: [`run_live_gateway_eval.py`](./run_live_gateway_eval.py)
- Repeat runner: [`run_live_gateway_eval_repeat.py`](./run_live_gateway_eval_repeat.py)
- Pytest entry: [`test_live_gateway_eval.py`](./test_live_gateway_eval.py)
- Support module: [`live_gateway_eval_support.py`](./live_gateway_eval_support.py)

## Coverage

The default live dataset covers:

- nominal committed cases for `reactor_01` and `agv_01`
- unsafe cases for `reactor_01`, `agv_01`, and `robot_arm_01`
- integrity rejections such as policy mismatch, expired timestamp, future
  timestamp, sensor divergence, and sensor hash mismatch
- interface-level failures such as `401`, `422`, and unknown-asset sensor
  errors

## Current Live Status

The suite is maintained against the current stack behavior, not historical
defects.

- The latest healthy-stack expectation is a clean `14/14` pass on the default
  dataset.
- The historical March 12, 2026 OT commit defect for `reactor_01` and
  `agv_01` safe commands has been resolved and is no longer treated as an
  expected failure.
- The robot live case now includes `target_positions`, so the Isaac Sim
  validator consumes the same semantic target intended by the dataset.
- The default robot case remains on a strong `UNSAFE` path rather than a
  nominal commit path because robot reverify can still be more timing-sensitive
  than the reactor and AGV flows in live mode.

## How To Run

Run the CLI evaluator:

```powershell
python tests/e2e/run_live_gateway_eval.py
```

Run through pytest:

```powershell
$env:PCAG_RUN_LIVE_E2E = "1"
pytest tests/e2e/test_live_gateway_eval.py -q
```

Run a repeated stability evaluation:

```powershell
python tests/e2e/run_live_gateway_eval_repeat.py --runs 10
```

## Result Files

- Single-run result:
  [`results/live_gateway_eval_latest.json`](./results/live_gateway_eval_latest.json)
- Repeat summary:
  [`results/live_gateway_eval_repeat_latest.json`](./results/live_gateway_eval_repeat_latest.json)

The repeat summary reports:

- `overall_accuracy_pct`: passed case executions divided by total case
  executions across all runs
- `loss_rate_pct`: failed case executions divided by total case executions
- `run_success_rate_pct`: share of runs with zero failed cases
- `per_case.pass_rate_pct`: per-case pass rate across repeated runs
- `status_groups`: grouped accuracy by expected result class such as
  `COMMITTED`, `UNSAFE`, `REJECTED`, and `ERROR`

## Dataset Authoring Guide

For a normal committed case, only a small semantic payload is usually needed:

```json
{
  "case_id": "reactor_safe_commit",
  "asset_id": "reactor_01",
  "proof": {
    "action_sequence_ref": "reactor_heat_60"
  },
  "expected": {
    "http_status": 200,
    "status": "COMMITTED",
    "response_has_evidence_ref": true,
    "evidence_required": true
  }
}
```

For an integrity rejection, override only the condition under test:

```json
{
  "case_id": "timestamp_expired_rejected",
  "asset_id": "reactor_01",
  "proof": {
    "action_sequence_ref": "reactor_heat_60",
    "timestamp_offset_ms": -10000
  },
  "expected": {
    "http_status": 200,
    "status": "REJECTED",
    "reason_code": "INTEGRITY_TIMESTAMP_EXPIRED"
  }
}
```

For robot-arm cases that should drive Isaac Sim semantics directly, include
`target_positions` inside the referenced action payload so the simulation layer
receives an explicit joint target vector.
