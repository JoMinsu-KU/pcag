from __future__ import annotations

from pcag.plugins.simulation.discrete_event import DiscreteEventBackend


def _base_backend_config() -> dict:
    return {
        "grid": {"width": 12, "height": 10, "obstacles": [], "intersections": [[6, 5], [6, 6], [5, 5], [7, 5]]},
        "agvs": {
            "agv_01": {"position": [2, 5], "speed": 1.0},
            "agv_02": {"position": [6, 8], "speed": 1.0},
        },
        "min_distance": 1.0,
        "visualization": {"enabled": False},
    }


def test_discrete_event_staggered_crossing_is_safe() -> None:
    backend = DiscreteEventBackend()
    config = _base_backend_config()
    config["agvs"]["agv_02"]["path"] = [[6, 8], [6, 8], [6, 8], [6, 7], [6, 6], [6, 5], [6, 4]]
    backend.initialize(config)

    result = backend.validate_trajectory(
        current_state={"position_x": 2, "position_y": 5, "agv_02": {"x": 6, "y": 8}},
        action_sequence=[
            {
                "action_type": "move_to",
                "params": {
                    "agv_id": "agv_01",
                    "target_x": 9,
                    "target_y": 5,
                    "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5]],
                },
            }
        ],
        constraints={"ruleset": []},
    )

    assert result["verdict"] == "SAFE"
    assert result["details"]["deadlock_detected"] is False
    assert result["details"]["edge_conflicts"] == []


def test_discrete_event_edge_swap_is_unsafe() -> None:
    backend = DiscreteEventBackend()
    config = _base_backend_config()
    config["agvs"] = {
        "agv_01": {"position": [8, 2], "speed": 1.0},
        "agv_02": {"position": [9, 2], "speed": 1.0, "path": [[8, 2]]},
    }
    backend.initialize(config)

    result = backend.validate_trajectory(
        current_state={"position_x": 8, "position_y": 2, "agv_02": {"x": 9, "y": 2}},
        action_sequence=[
            {
                "action_type": "move_to",
                "params": {"agv_id": "agv_01", "target_x": 9, "target_y": 2, "path": [[9, 2]]},
            }
        ],
        constraints={"ruleset": []},
    )

    assert result["verdict"] == "UNSAFE"
    assert ["agv_01", "agv_02"] in result["details"]["edge_conflicts"]


def test_discrete_event_deadlock_cycle_is_unsafe() -> None:
    backend = DiscreteEventBackend()
    config = _base_backend_config()
    config["agvs"] = {
        "agv_01": {"position": [5, 5], "speed": 1.0},
        "agv_02": {"position": [6, 5], "speed": 1.0, "path": [[7, 5]]},
        "agv_03": {"position": [7, 5], "speed": 1.0, "path": [[5, 5]]},
    }
    backend.initialize(config)

    result = backend.validate_trajectory(
        current_state={
            "position_x": 5,
            "position_y": 5,
            "agv_02": {"x": 6, "y": 5},
            "agv_03": {"x": 7, "y": 5},
        },
        action_sequence=[
            {
                "action_type": "move_to",
                "params": {"agv_id": "agv_01", "target_x": 6, "target_y": 5, "path": [[6, 5]]},
            }
        ],
        constraints={"ruleset": []},
    )

    assert result["verdict"] == "UNSAFE"
    assert result["details"]["deadlock_detected"] is True
    assert any(sorted(cycle) == ["agv_01", "agv_02", "agv_03"] for cycle in result["details"]["deadlock_cycles"])
