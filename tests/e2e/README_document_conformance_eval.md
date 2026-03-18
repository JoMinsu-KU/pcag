# Document-Conformance E2E Evaluation

This suite is meant for the document-conformance changes that were added to the
gateway path. It runs without starting the full service stack because it uses a
dataset-driven mock transport for downstream services.

## What gets verified

- Proof Package request contract
- Policy-version integrity rejection
- Initial `sensor_snapshot_hash` mismatch rejection at L1 integrity
- Timestamp freshness and future-timestamp rejection
- Sensor divergence handling when `sensor_snapshot` is present
- Safety `UNSAFE` handling and policy-derived `alternative_actions`
- 2PC failure paths such as `LOCK_DENIED`, reverify failure, and commit timeout
- Evidence ledger fail-hard behavior on non-2xx append responses
- Policy-driven `lock_ttl_ms` propagation into `PREPARE`

## Dataset structure

The file [document_conformance_eval_30.json](/C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/document_conformance_eval_30.json) has four sections:

- `meta`: Dataset metadata
- `defaults`: Default request shape, mock behavior, and expected assertions
- `libraries`: Reusable action sequences, asset profiles, and sensor snapshots
- `cases`: The 30 evaluation items

Each case only needs to override what is different. The runner automatically
creates a full `ControlRequest` body from:

- `asset_id`
- `proof.action_sequence_ref`
- `proof.timestamp_offset_ms`
- `proof.sensor_hash_mode`
- optional `proof.sensor_snapshot_ref`
- `mock.active_policy_version`
- `mock.asset_profile_ref`
- `mock.sensor_sequence_ref`

## Example case

```json
{
  "case_id": "policy_version_mismatch_rejected",
  "category": "integrity",
  "description": "Reject when proof policy version differs from active policy.",
  "proof": {
    "policy_version_id": "v-WRONG-VERSION"
  },
  "expected": {
    "http_status": 200,
    "status": "REJECTED",
    "reason_code": "INTEGRITY_POLICY_MISMATCH",
    "must_include_stages": ["RECEIVED", "SCHEMA_VALIDATED", "INTEGRITY_REJECTED"],
    "must_not_call_paths": ["/validate", "/prepare", "/commit"],
    "response_has_evidence_ref": false
  }
}
```

## How to run

Pytest mode:

```powershell
pytest tests/e2e/test_document_conformance_eval.py -q
```

Report mode:

```powershell
python tests/e2e/run_document_conformance_eval.py
```

The report runner writes a JSON summary to:

- [document_conformance_eval_30_latest.json](/C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/results/document_conformance_eval_30_latest.json)

## Input guidance

If you want to add new evaluation items, prefer adding a new `case` instead of
writing a raw request body by hand.

- Use `proof.timestamp_offset_ms` instead of hardcoding `timestamp_ms`
- Use `proof.action_sequence_ref` instead of repeating action JSON
- Use `mock.sensor_sequence_ref` to control first-read and reverify behavior
- Use `expected.must_include_stages` and `expected.must_not_call_paths` to make
  each case self-checking
