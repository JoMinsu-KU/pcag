"""
Executor Interface Definition
=============================
Defines the interface for executing commands on physical devices or simulation environments.
Used by the OT Interface service to abstract away the underlying communication protocol (e.g., Modbus, OPC UA, HTTP).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class IExecutor(ABC):
    """
    Abstract base class for Executors.
    """

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the executor with configuration.
        
        Args:
            config: Configuration dictionary (e.g., connection details, mappings).
        """
        pass

    @abstractmethod
    def execute(self, transaction_id: str, asset_id: str, action_sequence: List[Dict[str, Any]]) -> bool:
        """
        Execute a sequence of actions on the target asset.
        
        Args:
            transaction_id: The unique ID of the transaction.
            asset_id: The ID of the asset to control.
            action_sequence: A list of action dictionaries (e.g., {"type": "write", "register": 100, "value": 1}).
            
        Returns:
            bool: True if execution was successful, False otherwise.
        """
        pass

    @abstractmethod
    def safe_state(self, asset_id: str) -> bool:
        """
        Transition the specified asset to a safe state.
        This is called during Abort or E-Stop scenarios.
        
        Args:
            asset_id: The ID of the asset.
            
        Returns:
            bool: True if the safe state command was successfully sent.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """
        Clean up resources and close connections.
        """
        pass
