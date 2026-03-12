# PCAG Microservices (Apps)

The `pcag/apps/` directory contains the 7 core microservices that make up the Proof-Carrying Action Gateway (PCAG) architecture. Each service is responsible for a distinct phase of the verification pipeline or system administration.

## Core Microservices

1.  **Gateway Core (`gateway/`)**
    *   **Purpose:** The central orchestrator. Receives control requests from AI agents, validates the Proof Package schema, checks data integrity, initiates safety verification, coordinates the 2-Phase Commit (2PC) protocol, and logs evidence.
    *   **Pipeline Stages:** [100] Schema Validation → [110] Integrity Verification → [120] Safety Validation → [130] 2PC Execution → [140] Evidence Recording.

2.  **Safety Cluster (`safety_cluster/`)**
    *   **Purpose:** The deterministic safety validation engine. Evaluates proposed actions against physical limits, mathematical models (CBFs), and predictive simulations (e.g., Isaac Sim). Aggregates results using a SIL-based dynamic Consensus Engine.

3.  **Policy Store (`policy_store/`)**
    *   **Purpose:** The source of truth for safety constraints. Stores and serves versioned safety policies, asset profiles (SIL levels, thresholds), and consensus configurations.

4.  **Policy Admin (`policy_admin/`)**
    *   **Purpose:** Administrative interface for managing the Policy Store. Provides endpoints to create, update, and activate new policy versions securely.

5.  **Sensor Gateway (`sensor_gateway/`)**
    *   **Purpose:** The single point of contact for physical sensor data. Fetches real-time sensor snapshots from assets (via plugins) and provides them to the Gateway Core for Integrity (TOCTOU) checks.

6.  **OT Interface (`ot_interface/`)**
    *   **Purpose:** The execution layer connecting PCAG to physical assets (PLCs, robot controllers). Manages the 2-Phase Commit (2PC) protocol, acquiring input suppression locks (PREPARE) and executing verified commands (COMMIT).

7.  **Evidence Ledger (`evidence_ledger/`)**
    *   **Purpose:** An immutable, cryptographically verifiable log of all control transactions. Records each stage of the verification pipeline using a hash chain to ensure auditability and post-incident analysis.

## Architecture and Interaction

The Gateway Core is the primary entry point. It calls the other services over HTTP/REST according to the 5-stage pipeline defined in its orchestrator.

## Usage

Each microservice is a standalone FastAPI application. They are typically started concurrently using the provided utility scripts.

```bash
# Start all microservices (for local development/testing)
python scripts/start_services.py

# Or start a single service individually
uvicorn pcag.apps.gateway.main:app --port 8000 --reload
```

## Configuration

Service URLs and connection parameters are managed in the central `config/services.yaml` file.