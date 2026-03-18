"""
Isaac Sim proxy that talks to the dedicated worker process.

The proxy lives inside the Safety Cluster process, while Isaac Sim itself
stays isolated in a separate spawned process. Queue RPC is serialized with
an internal lock so concurrent FastAPI requests cannot mix responses.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import threading
import uuid

from pcag.core.ports.simulation_backend import ISimulationBackend

logger = logging.getLogger(__name__)


class IsaacSimProxy(ISimulationBackend):
    """Queue-based proxy for the dedicated Isaac Sim worker process."""

    def __init__(self):
        self._enabled = os.environ.get("PCAG_ENABLE_ISAAC", "false").lower() == "true"
        self._proc = None
        self._req_q = None
        self._res_q = None
        self._initialized = False
        self._timeout_s = 30
        self._rpc_lock = threading.Lock()

    def is_initialized(self) -> bool:
        """Return whether the worker process is alive and ready."""
        return self._initialized and self._proc is not None and self._proc.is_alive()

    def initialize(self, config: dict) -> None:
        """Start the dedicated Isaac Sim worker process."""
        if self._initialized:
            logger.info("Isaac Sim Proxy already initialized")
            return

        if not self._enabled:
            logger.info("Isaac Sim disabled (PCAG_ENABLE_ISAAC != true)")
            return

        self._timeout_s = config.get("timeout_ms", 30000) / 1000

        logger.info("Starting Isaac Sim Worker process...")

        ctx = mp.get_context("spawn")
        self._req_q = ctx.Queue()
        self._res_q = ctx.Queue()
        self._proc = ctx.Process(
            target=self._worker_entry,
            args=(self._req_q, self._res_q, config),
            daemon=True,
        )
        self._proc.start()

        try:
            boot_msg = self._res_q.get(timeout=120)
            if boot_msg.get("ok"):
                self._initialized = True
                logger.info("Isaac Sim Worker ready: %s", boot_msg.get("message"))
            else:
                logger.error("Isaac Sim Worker boot failed: %s", boot_msg.get("error"))
                self._cleanup()
        except Exception as exc:
            logger.error("Isaac Sim Worker boot timeout: %s", exc)
            self._cleanup()

    @staticmethod
    def _worker_entry(req_q, res_q, config):
        """Worker process bootstrap entrypoint."""
        from pcag.apps.safety_cluster.isaac_worker import isaac_worker_main

        isaac_worker_main(req_q, res_q, config)

    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict,
    ) -> dict:
        """Submit one simulation job to the worker and wait for the reply."""
        if not self.is_initialized():
            return self._indeterminate_result("Isaac Sim Worker not available")

        job_id = uuid.uuid4().hex
        try:
            message = self._round_trip(
                request={
                    "job_id": job_id,
                    "state": current_state,
                    "actions": action_sequence,
                    "constraints": constraints,
                    "world_ref": constraints.get("world_ref"),
                },
                timeout_s=self._timeout_s,
            )
        except Exception as exc:
            logger.error("Isaac Worker timeout/error: %s", exc)
            return self._indeterminate_result(f"Worker communication error: {exc}")

        if message.get("job_id") != job_id:
            logger.error("Job ID mismatch: expected %s, got %s", job_id, message.get("job_id"))
            return self._indeterminate_result("Worker returned mismatched job_id")

        if message.get("ok"):
            return message["result"]

        logger.error("Isaac Worker error: %s", message.get("error"))
        return self._indeterminate_result(f"Worker error: {message.get('error')}")

    def get_current_state(self) -> dict:
        """Query current world state from the worker."""
        if not self.is_initialized():
            return {}

        job_id = uuid.uuid4().hex
        try:
            message = self._round_trip(
                request={"type": "GET_STATE", "job_id": job_id},
                timeout_s=5.0,
            )
        except Exception as exc:
            logger.error("GET_STATE timeout/error: %s", exc)
            return {}

        if message.get("job_id") == job_id and message.get("ok"):
            return message["result"]

        logger.error("GET_STATE failed: %s", message.get("error"))
        return {}

    def shutdown(self) -> None:
        """Stop the worker process."""
        logger.info("Shutting down Isaac Sim Proxy...")
        if self._proc and self._proc.is_alive():
            try:
                self._req_q.put({"type": "SHUTDOWN"})
                self._proc.join(timeout=15)
                if self._proc.is_alive():
                    self._proc.terminate()
                    logger.warning("Isaac Worker terminated forcefully")
            except Exception as exc:
                logger.error("Worker shutdown error: %s", exc)

        self._cleanup()
        logger.info("Isaac Sim Proxy shutdown complete")

    def _cleanup(self):
        """Reset proxy runtime state."""
        self._proc = None
        self._req_q = None
        self._res_q = None
        self._initialized = False

    def _round_trip(self, *, request: dict, timeout_s: float) -> dict:
        """
        Serialize queue RPC so concurrent HTTP requests cannot interleave
        request/response pairs on the shared worker queues.
        """
        with self._rpc_lock:
            self._req_q.put(request)
            return self._res_q.get(timeout=timeout_s)

    @staticmethod
    def _indeterminate_result(reason: str) -> dict:
        return {
            "verdict": "INDETERMINATE",
            "engine": "isaac_sim",
            "common": {
                "first_violation_step": None,
                "violated_constraint": None,
                "latency_ms": 0,
                "steps_completed": 0,
            },
            "details": {"reason": reason},
        }
