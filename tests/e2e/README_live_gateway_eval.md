# Live Gateway E2E Evaluation

This suite validates the real running PCAG services with a single-entry flow:
the test only sends a request to the Gateway, and the rest of the pipeline is
executed by the live services.

## Interfaces verified

The runner checks the real interfaces before execution:

- `Gateway`: `http://127.0.0.1:8000/v1/control-requests`
- `Safety Cluster`: `http://127.0.0.1:8001/v1/validate`
- `Policy Store`: `http://127.0.0.1:8002/v1/policies/active`
- `Sensor Gateway`: `http://127.0.0.1:8003/v1/assets/{asset_id}/snapshots/latest`
- `OT Interface`: `http://127.0.0.1:8004/v1/prepare`, `/commit`, `/abort`
- `Evidence Ledger`: `http://127.0.0.1:8005/v1/transactions/{transaction_id}`
- `Policy Admin`: `http://127.0.0.1:8006/openapi.json`

The runner defaults to `127.0.0.1` instead of `localhost` because on some
Windows environments `localhost` tries IPv6 (`::1`) first, which can add a
few seconds of retry delay when the services only listen on IPv4.

## Single-entry design

You do not need to hand-write a full `proof_package` for each case.

Each dataset case only declares:

- `asset_id`
- `proof.action_sequence_ref`
- optional high-level proof overrides such as timestamp offset or explicit policy mismatch
- expected Gateway result and evidence expectations

The runner automatically fetches and fills:

- active `policy_version_id`
- latest `sensor_snapshot_hash`
- latest `sensor_reliability_index`
- current `timestamp_ms`

## Dataset file

- [live_gateway_eval_dataset.json](/C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/live_gateway_eval_dataset.json)

The current live dataset covers:

- committed cases for `reactor_01` and `agv_01`
- unsafe cases for `reactor_01`, `agv_01`, and `robot_arm_01`
- rejected integrity cases such as policy mismatch, expired timestamp, future timestamp, and sensor divergence
- interface-level failures such as `422`, `401`, and unknown asset sensor errors

Current note:

- the robot-arm live case includes `target_positions` so that the Isaac Sim validator consumes the same semantic target that the dataset intends
- the runner defaults to `127.0.0.1` to avoid Windows IPv6 retry delays on `localhost`

## How to run

CLI runner:

```powershell
python tests/e2e/run_live_gateway_eval.py
```

Pytest mode:

```powershell
$env:PCAG_RUN_LIVE_E2E = "1"
pytest tests/e2e/test_live_gateway_eval.py -q
```

Results are saved to:

- [live_gateway_eval_latest.json](/C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/results/live_gateway_eval_latest.json)

Repeat runner for stability metrics:

```powershell
python tests/e2e/run_live_gateway_eval_repeat.py --runs 10
```

Repeat results are saved to:

- [live_gateway_eval_repeat_latest.json](/C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/results/live_gateway_eval_repeat_latest.json)

The repeat summary reports:

- `overall_accuracy_pct`: passed case executions / total case executions across all runs
- `loss_rate_pct`: failed case executions / total case executions across all runs
- `run_success_rate_pct`: percentage of runs with zero failed cases
- `per_case.pass_rate_pct`: per-case pass rate across repeated runs
- `status_groups`: grouped accuracy by expected result class such as `COMMITTED`, `UNSAFE`, `REJECTED`, `ERROR`

## Dataset authoring guide

For a normal committed case, you usually only need this:

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

For an integrity rejection, override only the semantic knob you want:

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

## Current live finding

The current environment was checked before building this suite. One important
observation is that a nominal `robot_arm_01` move can become flaky in live mode
because the second sensor read during reverify may drift enough to trigger
`REVERIFY_HASH_MISMATCH`. For that reason, the default live dataset keeps the
robot case on the stable `UNSAFE` path instead of a nominal commit path.

The first live run on March 12, 2026 also exposed a real integration issue:
safe `reactor_01` and `agv_01` commands reached `REVERIFY_PASSED` but then
failed at OT commit with `COMMIT_FAILED` because the OT Interface returned HTTP
500. Those committed cases are intentionally kept as `COMMITTED` expectations so
the live suite continues to detect that defect until it is fixed.
