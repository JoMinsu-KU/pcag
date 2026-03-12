"""
Executor Manager
================
Manages the lifecycle and retrieval of Executor instances.
Loads configuration from 'executor_mappings.yaml' and instantiates
the appropriate executor (Mock or Modbus) for each asset.
"""

import logging
import os
from typing import Dict, Optional
from pcag.core.ports.executor import IExecutor
from pcag.plugins.executor.mock_executor import MockExecutor
from pcag.plugins.executor.modbus_executor import ModbusExecutor
from pcag.core.utils.config_loader import load_config

logger = logging.getLogger(__name__)

class ExecutorManager:
    _instances: Dict[str, IExecutor] = {}
    _config_cache: dict = {}
    _config_loaded: bool = False

    @classmethod
    def _load_registry(cls):
        """
        Load configuration once.
        """
        if not cls._config_loaded:
            try:
                cls._config_cache = load_config("executor_mappings.yaml")
                cls._config_loaded = True
            except Exception as e:
                logger.critical(f"Failed to load executor mappings: {e}")
                raise e

    @classmethod
    def get_executor(cls, asset_id: str) -> IExecutor:
        """
        Get the executor instance responsible for the given asset_id.
        """
        if not cls._config_loaded:
            cls._load_registry()
            
        config = cls._config_cache
        
        # 1. Resolve executor name for the asset
        asset_map = config.get("asset_map", {})
        # Fail-Hard: No default mock fallback. Must be explicitly configured.
        executor_name = asset_map.get(asset_id)
        
        if not executor_name:
             logger.critical(f"[SYSTEM_ERROR] No executor mapped for asset {asset_id}")
             raise RuntimeError(f"No executor mapped for asset {asset_id}")
        
        # 2. Return existing instance if available
        if executor_name in cls._instances:
            return cls._instances[executor_name]
            
        # 3. Create new instance
        executors_conf = config.get("executors", {})
        executor_conf = executors_conf.get(executor_name)
        
        if not executor_conf:
             logger.critical(f"[SYSTEM_ERROR] No configuration found for executor '{executor_name}'")
             raise ValueError(f"No configuration found for executor '{executor_name}'")
            
        etype = executor_conf.get("type", "mock")
        econfig = executor_conf.get("config", {})
        
        logger.info(f"Initializing executor '{executor_name}' of type '{etype}'")
        
        if etype == "modbus":
            executor = ModbusExecutor()
        elif etype == "mock":
            if os.environ.get("PCAG_ENV") == "production":
                 logger.critical(f"[SECURITY] Executor '{executor_name}' uses MOCK type, forbidden in PRODUCTION.")
                 raise RuntimeError(f"Executor '{executor_name}' uses MOCK type, forbidden in PRODUCTION.")
            executor = MockExecutor()
        else:
             # Unknown type, default to mock or error?
             # Better to error in production.
             raise ValueError(f"Unknown executor type '{etype}'")
            
        try:
            executor.initialize(econfig)
            cls._instances[executor_name] = executor
            return executor
        except Exception as e:
            logger.critical(f"[SYSTEM_ERROR] Failed to initialize executor '{executor_name}': {e}", exc_info=True)
            # FAIL-SAFE: Do NOT fallback to mock for physical execution failure.
            raise RuntimeError(f"Failed to initialize executor '{executor_name}': {e}")

    @classmethod
    def reset(cls):
        """Shutdown all executors and clear registry."""
        for name, executor in cls._instances.items():
            try:
                executor.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down executor {name}: {e}")
        cls._instances.clear()
