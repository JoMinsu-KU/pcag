# PCAG Package Guide

The `pcag/` package contains the implementation of the PCAG system itself.
It is the core software artifact of the repository and houses the service applications, shared contracts, validation logic, database models, and runtime plugins.

If the top-level [`README.md`](../README.md) explains what PCAG is, this document explains where the implementation lives and how the package is organized.

## Package Structure

| Directory | Role |
| --- | --- |
| [`apps/`](apps/README.md) | FastAPI microservices and service entrypoints |
| [`core/`](core/README.md) | Shared contracts, data models, middleware, validators, consensus, and infrastructure utilities |
| [`plugins/`](plugins/README.md) | Concrete executor, sensor, and simulation backend implementations |

## Architectural Layers

The package is intentionally layered.

### 1. Application layer

The service applications in [`apps/`](apps/README.md) expose external HTTP interfaces and orchestrate runtime behavior.
Examples:

- Gateway
- Safety Cluster
- Sensor Gateway
- OT Interface
- Evidence Ledger
- PLC Adapter
- Dashboard

### 2. Shared logic layer

The reusable logic in [`core/`](core/README.md) holds:

- request and response contracts
- database access models
- validation engines
- consensus logic
- canonicalization and hashing utilities
- logging middleware

This is where the system semantics are defined.

### 3. Backend implementation layer

The implementations in [`plugins/`](plugins/README.md) translate abstract interfaces into concrete backends:

- PLC and Modbus execution
- Isaac-based sensor reads
- ODE and discrete-event simulation
- PLC Adapter-backed field I/O

## What Lives Here Conceptually

The `pcag/` package is not just a collection of validators.
It implements an end-to-end deterministic execution stack:

1. request contract handling
2. integrity validation
3. parallel safety validation
   - Rules, barrier-based validation, and simulation
4. transactional execution control
5. evidence-backed auditability
6. centralized field I/O
7. operational monitoring

That is the main reason the repository is more than a paper prototype.

It is also why the public artifact should be read as a hybrid runtime stack:
some paths are fully live-backed, some are simulation-backed, and some remain
explicitly mock-backed in the reference configuration.

## Reading Guide

If you want to understand the system from code instead of from papers, a good reading order is:

1. [`../README.md`](../README.md)
2. [`apps/gateway/routes.py`](apps/gateway/routes.py)
3. [`core/services/integrity_service.py`](core/services/integrity_service.py)
4. [`apps/safety_cluster/service.py`](apps/safety_cluster/service.py)
5. [`core/services/consensus_engine.py`](core/services/consensus_engine.py)
6. [`apps/ot_interface/routes.py`](apps/ot_interface/routes.py)
7. [`apps/evidence_ledger/routes.py`](apps/evidence_ledger/routes.py)
8. [`apps/plc_adapter/service.py`](apps/plc_adapter/service.py)

## Recommended Module Docs

- [`apps/README.md`](apps/README.md)
- [`core/README.md`](core/README.md)
- [`plugins/README.md`](plugins/README.md)

## Notes for Contributors

- Most runtime semantics belong in `core`, not directly in service routes.
- Service routes should orchestrate decisions, not duplicate validator logic.
- Plugin code should stay backend-focused and avoid absorbing policy semantics that belong to `core`.
