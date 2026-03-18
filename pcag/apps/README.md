# Service Applications

The `pcag/apps/` directory contains the concrete microservices that make up the PCAG runtime.
Each service is a FastAPI application with a well-scoped responsibility inside the deterministic execution architecture.

The services are intentionally separated so that policy retrieval, sensing, safety validation, execution control, evidence recording, and monitoring can evolve independently while still composing into a single pipeline.

## Service Map

| Service | Port | Main Responsibility |
| --- | --- | --- |
| `gateway` | 8000 | Orchestrates the full execution pipeline |
| `safety_cluster` | 8001 | Runs Rules, barrier-based validation, Simulation, and consensus |
| `policy_store` | 8002 | Serves active policies and asset profiles |
| `sensor_gateway` | 8003 | Returns live snapshots and hashes |
| `ot_interface` | 8004 | Owns `PREPARE`, `COMMIT`, `ABORT`, and `E-Stop` |
| `evidence_ledger` | 8005 | Stores append-only evidence events |
| `policy_admin` | 8006 | Registers and activates policy versions |
| `plc_adapter` | 8007 | Centralized PLC and Modbus I/O |
| `dashboard` | 8008 | Live operational monitoring UI and APIs |

## Service Directory Guide

### [`gateway/`](gateway)

The Gateway is the main orchestration service.
It is the entrypoint for external control requests and implements the top-level fail-closed pipeline:

- schema validation
- integrity validation
- safety validation dispatch
- transactional execution control
- evidence emission

If you only read one service in the repository, start here.

### [`safety_cluster/`](safety_cluster)

The Safety Cluster is responsible for evaluating whether a command is safe under current conditions.

It currently provides:

- Rules validation
- barrier-based validation through the current static CBF-style layer
- Simulation validation
- SIL-aware consensus
- Isaac worker/proxy isolation

This service runs in the separate `pcag-isaac` environment because of Isaac runtime requirements.

### [`policy_store/`](policy_store)

The Policy Store is the source of truth for active policy versions and asset profiles.
It supports immutable policy versioning and is queried by the Gateway during live request handling.

### [`policy_admin/`](policy_admin)

The Policy Admin service manages policy registration and activation.
It is the administrative interface for evolving policy versions without mutating the meaning of already-recorded evidence.

### [`sensor_gateway/`](sensor_gateway)

The Sensor Gateway provides the latest observable state for each asset.

Depending on the asset, this may involve:

- Isaac-based robot state retrieval
- PLC Adapter-backed field reads
- mock or synthetic sensor sources for evaluation

The Gateway depends on this service both for the initial integrity check and for re-verification.

### [`ot_interface/`](ot_interface)

The OT Interface controls execution authority and transactional state.

It owns:

- `PREPARE`
- `COMMIT`
- `ABORT`
- `E-Stop`
- lock ownership and expiration

This service is where "execution semantics" become concrete.

### [`evidence_ledger/`](evidence_ledger)

The Evidence Ledger stores append-only evidence events with hash-chain linkage.
It is critical for reproducibility, forensics, and paper-oriented auditability claims.

### [`plc_adapter/`](plc_adapter)

The PLC Adapter centralizes PLC and Modbus access.
This prevents field I/O from being scattered across the codebase and reduces connection-management instability.

### [`dashboard/`](dashboard)

The Dashboard provides live operational visibility across the system:

- health probes
- recent transactions
- evidence summaries
- live logs
- PLC state
- evaluation summaries

## Runtime Split

Most services run in the `pcag` environment.
Only the Safety Cluster and Isaac worker path belong in `pcag-isaac`.

This split is not accidental; it reflects the operational constraints of Isaac Sim and keeps the rest of the stack easier to run and test.

## Reading Guide

For system understanding, a practical order is:

1. [`gateway/`](gateway)
2. [`safety_cluster/`](safety_cluster)
3. [`ot_interface/`](ot_interface)
4. [`evidence_ledger/`](evidence_ledger)
5. [`plc_adapter/`](plc_adapter)
6. [`dashboard/`](dashboard)

## Related Documentation

- [`../README.md`](../README.md)
- [`../core/README.md`](../core/README.md)
- [`../plugins/README.md`](../plugins/README.md)
- [`../../scripts/README.md`](../../scripts/README.md)
