# PCAG Core Logic (`core/`)

The `pcag/core/` directory contains the foundational business logic, data structures, and utilities that power the Proof-Carrying Action Gateway (PCAG) microservices. It abstracts the complex deterministic safety checks, cryptographic hashing, and data interchange formats into reusable components.

## Directory Structure

*   `contracts/`: Pydantic data models (Data Transfer Objects) defining the structure of API requests and responses (Proof Packages, Evidence Payloads, Control Requests).
*   `database/`: Database engines and SQLAlchemy ORM models for persistent storage (Evidence Ledger, Policy Store).
*   `middleware/`: FastAPI middleware components for authentication (API keys) and centralized logging.
*   `models/`: Internal domain models representing system state, policies, consensus results, and proof evidence.
*   `ports/`: Interfaces (abstract base classes) defining how PCAG interacts with external systems like sensors, simulators, and OT executors.
*   `services/`: The core algorithms and business logic for safety validation.
    *   **`cbf_validator.py`**: Evaluates mathematical safety boundaries (Control Barrier Functions).
    *   **`consensus_engine.py`**: Aggregates validator results based on asset SIL levels (AND, WORST_CASE, WEIGHTED modes).
    *   **`integrity_service.py`**: Checks sensor divergence and data freshness.
    *   **`rules_validator.py`**: Verifies physical limits (thresholds, ranges).
    *   **`tx_state_machine.py`**: Manages the state transitions of the 2-Phase Commit (2PC) protocol.
*   `utils/`: Helper functions for canonicalization, hashing, logging configuration, and configuration loading.

## Usage

This module provides the core libraries used by the microservices in `pcag/apps/`. For example, the `safety_cluster` service relies heavily on the `services/` components to evaluate control actions, while the `gateway` uses `utils/` for cryptographic evidence logging.

```python
from pcag.core.services.consensus_engine import evaluate_consensus
from pcag.core.contracts.gateway import ControlRequest
from pcag.core.utils.hash_utils import compute_event_hash
```

## Related Files

*   `pcag/apps/`: Microservices that consume these core libraries.
*   `tests/unit/`: Unit tests ensuring the accuracy and reliability of the core deterministic logic.
