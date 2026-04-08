# PCAG IJAMT Label Taxonomy

Version: `v1`  
Status: frozen reference for benchmark generation and baseline evaluation

## 1. Purpose

This file defines the benchmark label system used by the IJAMT experiments.

Each benchmark case must define labels at three levels:

1. expected final status
2. expected stop stage
3. expected reason code

The benchmark should not treat correctness as a final-status-only problem.  
The stage and reason labels are required because PCAG is an execution-assurance system, not merely a binary classifier.

## 2. Final status labels

### `COMMITTED`

Use when the command is expected to complete the full deterministic execution path and be acknowledged as successfully executed.

Typical case types:

- nominal safe commands

### `UNSAFE`

Use when the command is expected to fail at the safety validation stage because it violates rules, barrier margins, or simulation-backed safety expectations.

Typical case types:

- unsafe counterfactual commands

### `REJECTED`

Use when the command is expected to be blocked before safety validation due to integrity-layer failure.

Typical case types:

- policy version mismatch
- stale timestamp
- sensor hash mismatch
- sensor divergence

### `ABORTED`

Use when the command passes early checks but is intentionally stopped before successful commit because of prepare, reverify, or commit-time recovery semantics.

Typical case types:

- lock denied
- reverify mismatch
- commit timeout
- recovered execution failure

### `ERROR`

Use when the system enters an infrastructure or unrecoverable execution-error path.

Typical case types:

- sensor gateway failure
- policy store failure
- irrecoverable commit path failure

## 3. Stop-stage labels

Stop-stage labels identify the terminal stage reached by a case.

### `HTTP_401`

Authentication rejected before pipeline entry.

### `HTTP_422`

Schema or contract failure before the semantic pipeline begins.

### `SCHEMA_VALIDATED`

Intermediate stage only.  
Should not be the terminal stop stage for released benchmark cases unless a dedicated schema experiment is intentionally designed.

### `INTEGRITY_REJECTED`

Terminal stage for integrity-layer rejection.

### `SAFETY_UNSAFE`

Terminal stage for safety-layer rejection.

### `PREPARE_LOCK_DENIED`

Terminal stage when prepare cannot secure the asset lock.

### `REVERIFY_FAILED`

Terminal stage when post-prepare revalidation fails.

### `COMMIT_FAILED`

Terminal stage when commit reaches the executor, receives a known execution-failure
result, and the case does not end in a clean commit.

### `COMMIT_ERROR`

Terminal stage when commit fails because of an infrastructure or transport
exception rather than a known execution-failure result.

### `COMMIT_TIMEOUT`

Terminal stage when commit acknowledgment is not obtained within the expected semantics.

### `COMMIT_ACK`

Terminal stage for successful execution and commit acknowledgment.

## 4. Reason-code labels

The benchmark should only use reason codes that correspond to real gateway, safety, or OT semantics.

### Integrity-layer reasons

- `INTEGRITY_POLICY_MISMATCH`
- `INTEGRITY_SENSOR_HASH_MISMATCH`
- `INTEGRITY_TIMESTAMP_EXPIRED`
- `INTEGRITY_TIMESTAMP_FUTURE`
- `INTEGRITY_SENSOR_DIVERGENCE`

### Safety-layer reasons

- `SAFETY_UNSAFE`

### Prepare / transaction reasons

- `LOCK_DENIED`
- `TOCTOU_REVERIFY_FAILED`
- `REVERIFY_HASH_MISMATCH`
- `COMMIT_FAILED`
- `COMMIT_TIMEOUT`

### Infrastructure / system reasons

- `POLICY_STORE_ERROR`
- `SENSOR_GATEWAY_ERROR`
- `SAFETY_CLUSTER_ERROR`
- `OT_INTERFACE_ERROR`
- `EVIDENCE_LEDGER_ERROR`

## 5. Label consistency rules

## 5.1 Final status to stop-stage consistency

The following combinations are valid.

| expected_final_status | allowed terminal stop stage |
| --- | --- |
| `COMMITTED` | `COMMIT_ACK` |
| `UNSAFE` | `SAFETY_UNSAFE` |
| `REJECTED` | `INTEGRITY_REJECTED` |
| `ABORTED` | `PREPARE_LOCK_DENIED`, `REVERIFY_FAILED`, `COMMIT_FAILED`, `COMMIT_TIMEOUT` |
| `ERROR` | `COMMIT_ERROR` or benchmark-specific infrastructure stop mapping |

## 5.2 Stop-stage to reason-code consistency

Recommended mappings:

| stop stage | expected reason code examples |
| --- | --- |
| `INTEGRITY_REJECTED` | integrity-family reason codes |
| `SAFETY_UNSAFE` | `SAFETY_UNSAFE` |
| `PREPARE_LOCK_DENIED` | `LOCK_DENIED` |
| `REVERIFY_FAILED` | `TOCTOU_REVERIFY_FAILED`, `REVERIFY_HASH_MISMATCH` |
| `COMMIT_FAILED` | `COMMIT_FAILED` |
| `COMMIT_ERROR` | `OT_INTERFACE_ERROR`, `COMMIT_ERROR` |
| `COMMIT_TIMEOUT` | `COMMIT_TIMEOUT` |
| `COMMIT_ACK` | `null` |

## 5.3 Null reason usage

`expected_reason_code = null` is allowed only when:

- the case is expected to commit cleanly, or
- the benchmark explicitly evaluates a transport-layer HTTP condition instead of a semantic reason code

## 6. Split-to-label expectations

### Nominal split

- expected final status should normally be `COMMITTED`
- stop stage should normally be `COMMIT_ACK`

### Unsafe split

- expected final status should normally be `UNSAFE`
- stop stage should normally be `SAFETY_UNSAFE`

### Fault split

- expected final status is usually `REJECTED`, `ABORTED`, or `ERROR`
- stop stage depends on the injected fault location

## 7. Benchmark evaluation fields

Each case record should include:

- `expected_final_status`
- `expected_stop_stage`
- `expected_reason_code`

The result collector should then compute:

- final-status match
- stop-stage match
- reason-code match

## 8. Examples

### Example A. Nominal committed case

```json
{
  "expected_final_status": "COMMITTED",
  "expected_stop_stage": "COMMIT_ACK",
  "expected_reason_code": null
}
```

### Example B. Unsafe robot joint case

```json
{
  "expected_final_status": "UNSAFE",
  "expected_stop_stage": "SAFETY_UNSAFE",
  "expected_reason_code": "SAFETY_UNSAFE"
}
```

### Example C. Stale timestamp case

```json
{
  "expected_final_status": "REJECTED",
  "expected_stop_stage": "INTEGRITY_REJECTED",
  "expected_reason_code": "INTEGRITY_TIMESTAMP_EXPIRED"
}
```

### Example D. Reverify mismatch case

```json
{
  "expected_final_status": "ABORTED",
  "expected_stop_stage": "REVERIFY_FAILED",
  "expected_reason_code": "REVERIFY_HASH_MISMATCH"
}
```

## 9. Frozen release rule

Before the first benchmark release:

- every released case must pass label consistency checks
- no case may use a stop-stage or reason code that is not defined here
- changes to this taxonomy require a version bump and regeneration note
