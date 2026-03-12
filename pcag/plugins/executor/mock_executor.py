"""
Mock Executor Plugin
====================
A dummy executor that logs actions instead of executing them on real hardware.
Used for testing and development when no physical device is available.
"""

import logging
import os
from typing import List, Dict, Any
from pcag.core.ports.executor import IExecutor

logger = logging.getLogger(__name__)

class MockExecutor(IExecutor):
    def __init__(self):
        self._config = {}

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        logger.info(f"MockExecutor initialized with config: {config}")

    def execute(self, transaction_id: str, asset_id: str, action_sequence: List[Dict[str, Any]]) -> bool:
        if os.environ.get("PCAG_ENV") == "production":
             raise RuntimeError("MockExecutor cannot be used in PRODUCTION environment")

        logger.warning(f"MockExecutor is being used — NO REAL EQUIPMENT CONTROL (asset: {asset_id})")
        
        for i, action in enumerate(action_sequence):
            logger.info(f"  Action [{i+1}/{len(action_sequence)}]: {action}")
        return True

    def safe_state(self, asset_id: str) -> bool:
        logger.info(f"MockExecutor: Transitioning asset {asset_id} to SAFE STATE")
        return True

    def shutdown(self) -> None:
        logger.info("MockExecutor: Shutdown")
