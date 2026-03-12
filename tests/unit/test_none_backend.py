"""Tests for None Simulation Backend."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.plugins.simulation.none_backend import NoneBackend
from pcag.core.ports.simulation_backend import ISimulationBackend


def test_none_is_simulation_backend():
    """NoneBackend should implement ISimulationBackend."""
    backend = NoneBackend()
    assert isinstance(backend, ISimulationBackend)


def test_none_initialize():
    """Initialize should do nothing without error."""
    backend = NoneBackend()
    backend.initialize({})


def test_none_always_indeterminate():
    """validate_trajectory should always return INDETERMINATE."""
    backend = NoneBackend()
    backend.initialize({})
    
    result = backend.validate_trajectory(
        current_state={"temperature": 150},
        action_sequence=[{"action_type": "set_heater", "params": {"value": 90}}],
        constraints={}
    )
    
    assert result["verdict"] == "INDETERMINATE"
    assert result["engine"] == "none"
    assert result["common"]["latency_ms"] == 0.0
    assert result["common"]["steps_completed"] == 0
    assert result["details"]["reason"] == "simulation_disabled"


def test_none_shutdown():
    """Shutdown should do nothing without error."""
    backend = NoneBackend()
    backend.shutdown()


def test_none_idempotent():
    """Multiple calls should return identical results."""
    backend = NoneBackend()
    backend.initialize({})
    
    result1 = backend.validate_trajectory({}, [], {})
    result2 = backend.validate_trajectory({"x": 1}, [{"action_type": "test", "params": {}}], {})
    
    assert result1["verdict"] == result2["verdict"] == "INDETERMINATE"
