# PCAG Test Suite (`tests/`)

The `tests/` directory contains a comprehensive automated test suite for the Proof-Carrying Action Gateway (PCAG). It uses `pytest` to ensure the deterministic safety logic, microservice orchestration, and integration with external systems (like Isaac Sim) function correctly and fail safely under adversarial conditions.

## Test Categories

The test suite is divided into three main layers:

### 1. Unit Tests (`tests/unit/`)
*   **Purpose:** Isolated testing of individual functions, classes, and core business logic without network or database dependencies.
*   **Key Coverage:**
    *   `test_consensus_engine.py`: Verifies SIL-based voting (AND, WORST_CASE, WEIGHTED) and edge cases.
    *   `test_cbf_validator.py`: Tests the mathematical bounds of Control Barrier Functions.
    *   `test_rules_validator.py`: Checks threshold, range, and physical limit evaluations.
    *   `test_hash_chain.py`: Validates the cryptographic integrity of the Evidence Ledger.
    *   `test_2pc_state_machine.py`: Ensures correct state transitions (PREPARE → REVERIFY → COMMIT/ABORT).
*   **Execution:** Fast (ms).

### 2. Integration Tests (`tests/integration/`)
*   **Purpose:** Tests the interaction between two or more internal PCAG components or a PCAG service and a mock external system (e.g., PostgreSQL).
*   **Key Coverage:**
    *   `test_pipeline_mock.py`: A mocked version of the 5-stage Gateway pipeline without full service orchestration.
    *   `test_postgres_integration.py`: Validates database schemas and queries for the Policy Store and Evidence Ledger.
*   **Execution:** Medium (seconds).

### 3. End-to-End (E2E) Tests (`tests/e2e/`)
*   **Purpose:** The most critical tests. They start all 7 microservices, seed the policies, and send complete `ProofPackage` requests through the actual HTTP interfaces, verifying the final execution and evidence logs.
*   **Key Coverage:**
    *   `test_three_scenarios.py`: Runs the reference architectures (Scenario A: Chemical Reactor, B: Robot Arm, C: AGV) end-to-end.
    *   `test_failhard_scenarios.py`: Intentionally sends expired timestamps, invalid schemas, and unsafe actions to verify the system "fails closed" deterministically.
*   **Execution:** Slow (tens of seconds). Requires `scripts/start_services.py` and `scripts/seed_policy.py`.

### 4. Specialized Tests (`tests/isaac_sim/`, `tests/modbus/`)
*   Tests specific to plugins, requiring the actual external software/hardware or sophisticated mocks (e.g., NVIDIA Isaac Sim API connections, Modbus TCP servers).

## Usage

```bash
# Run the entire test suite (unit + integration + mocked E2E)
pytest tests/

# Run only the unit tests (fast)
pytest tests/unit/

# Run the full end-to-end pipeline (requires services to be running)
pytest tests/e2e/test_all_scenarios.py -v
```

## Related Files
*   `tests/e2e/results/`: Output directory where E2E test results and trace logs are stored.
*   `pytest.ini`: Pytest configuration file (if present) to manage markers and default behaviors.
