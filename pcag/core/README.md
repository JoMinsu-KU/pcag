# Core Package Guide

The `pcag/core/` directory contains the shared semantics of the system.
If `pcag/apps/` defines the service boundaries, `pcag/core/` defines the contracts, rules, validators, and utilities that make the architecture deterministic and consistent.

This is the part of the repository that most directly captures the meaning of PCAG.

## Subpackages

| Directory | Purpose |
| --- | --- |
| `contracts/` | API and cross-service request/response models |
| `database/` | SQLAlchemy models and engine setup |
| `middleware/` | API-key enforcement and structured logging middleware |
| `models/` | Shared domain data structures |
| `ports/` | Abstract interfaces for sensors, executors, and simulation backends |
| `services/` | Integrity, Rules, CBF, consensus, alternative actions, and other reusable logic |
| `utils/` | Hashing, canonicalization, config loading, and logging utilities |

## Most Important Files

### Contracts

- [`contracts/gateway.py`](contracts/gateway.py)
  - Gateway request and response models
- [`contracts/proof_package.py`](contracts/proof_package.py)
  - The core request proof structure
- [`contracts/ot_interface.py`](contracts/ot_interface.py)
  - Transactional execution contracts
- [`contracts/evidence.py`](contracts/evidence.py)
  - Evidence append and query models
- [`contracts/plc_adapter.py`](contracts/plc_adapter.py)
  - PLC Adapter request and health models

### Validation and decision logic

- [`services/integrity_service.py`](services/integrity_service.py)
  - policy version, timestamp, divergence, and sensor hash checks
- [`services/rules_validator.py`](services/rules_validator.py)
  - discrete rules and forbidden combinations
- [`services/cbf_validator.py`](services/cbf_validator.py)
  - state projection and barrier checking
- [`services/consensus_engine.py`](services/consensus_engine.py)
  - SIL-aware consensus logic
- [`services/alternative_action.py`](services/alternative_action.py)
  - conservative safe-state-based alternative action generation

### Shared infrastructure

- [`utils/hash_utils.py`](utils/hash_utils.py)
  - hash-chain support and canonical hashing
- [`utils/config_loader.py`](utils/config_loader.py)
  - YAML loading for runtime config
- [`utils/logging_config.py`](utils/logging_config.py)
  - human-readable colored logging configuration
- [`middleware/logging_middleware.py`](middleware/logging_middleware.py)
  - access-log summarization and request context binding

## What Changed in the Current Implementation

The current implementation includes several semantics that are especially important for papers and audits:

- `sensor_snapshot_hash` mismatch is now a real L1 reject condition
- Gateway responses can include `alternative_actions`
- evidence responses include `created_at`
- logging is human-readable, service-aware, and source-aware
- commit semantics are fail-closed and only finalize after successful execution

## Design Intent

The guiding rule for this package is:

> system meaning should live in `core`, not be duplicated ad hoc inside service routes.

That means:

- validation semantics belong in `services/`
- request meaning belongs in `contracts/`
- backend-neutral abstractions belong in `ports/`
- shared infrastructure belongs in `utils/` and `middleware/`

## Good Entry Points for Reviewers

If you want to understand the semantics quickly, start with:

1. [`contracts/proof_package.py`](contracts/proof_package.py)
2. [`services/integrity_service.py`](services/integrity_service.py)
3. [`services/consensus_engine.py`](services/consensus_engine.py)
4. [`services/rules_validator.py`](services/rules_validator.py)
5. [`services/cbf_validator.py`](services/cbf_validator.py)

## Related Documentation

- [`../README.md`](../README.md)
- [`../apps/README.md`](../apps/README.md)
- [`../plugins/README.md`](../plugins/README.md)
