"""HTTP bridge to the persistent Isaac virtual executor, with explicit receipts."""
from __future__ import annotations
import httpx
import os
from pcag.core.ports.executor import IExecutor
from pcag.core.utils.config_loader import get_service_urls


class IsaacExecutor(IExecutor):
    def initialize(self, config):
        self.url = (config.get("url") or get_service_urls()["safety_cluster"]).rstrip("/")
        self.timeout = float(config.get("timeout_s", 60))
        self.last_error = None
        self.headers = {"X-API-Key": os.environ.get("PCAG_API_KEY_1", "pcag-agent-key-001")}

    def execute(self, transaction_id, asset_id, action_sequence):
        result = httpx.post(self.url + "/v1/revision/execute", json={"transaction_id": transaction_id, "asset_id": asset_id, "action_sequence": action_sequence}, timeout=self.timeout, headers=self.headers)
        result.raise_for_status()
        return result.json()

    def query_operation(self, *, transaction_id, asset_id):
        result = httpx.get(self.url + "/v1/revision/operation", params={"transaction_id": transaction_id, "asset_id": asset_id}, timeout=self.timeout, headers=self.headers)
        result.raise_for_status()
        return result.json()

    def safe_state(self, asset_id):
        # A hold in this kinematic virtual controller means keeping measured
        # positions and explicitly zeroing velocities. This is not a hardware
        # braking or certified safe-stop claim.
        try:
            state = httpx.get(self.url + "/v1/simulation/state", timeout=self.timeout).json()
            positions = state.get("joint_positions")
            if not positions:
                raise RuntimeError("No measured robot positions for virtual hold")
            response = httpx.post(self.url + "/v1/revision/state", json={"initial_state":{"joint_positions":positions}}, timeout=self.timeout, headers=self.headers)
            response.raise_for_status()
            observed = response.json()["current_state"]
            held = observed.get("joint_positions") or []
            velocities = observed.get("joint_velocities") or []
            success = len(held) == len(positions) and all(abs(a-b) < 1e-5 for a,b in zip(held, positions)) and bool(velocities) and all(abs(x) < 1e-5 for x in velocities)
            self.last_error = None if success else "Virtual hold readback did not confirm positions and zero velocity"
            return success
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def shutdown(self):
        pass
