from pcag.core.services.integrity_service import check_integrity
from pcag.core.models.common import DivergenceThreshold

def test_integrity_all_pass():
    res, err = check_integrity(
        proof_policy_version="v1",
        active_policy_version="v1",
        proof_timestamp_ms=1000,
        current_timestamp_ms=1200, # age 200
        timestamp_max_age_ms=500,
        proof_sensor_snapshot={"a": 10},
        current_sensor_snapshot={"a": 10},
        divergence_thresholds=[]
    )
    assert res is True
    assert err is None

def test_integrity_policy_mismatch():
    res, err = check_integrity(
        proof_policy_version="v1",
        active_policy_version="v2",
        proof_timestamp_ms=1000,
        current_timestamp_ms=1200,
        timestamp_max_age_ms=500,
        proof_sensor_snapshot={},
        current_sensor_snapshot={},
        divergence_thresholds=[]
    )
    assert res is False
    assert err == "INTEGRITY_POLICY_MISMATCH"

def test_integrity_timestamp_expired():
    res, err = check_integrity(
        proof_policy_version="v1",
        active_policy_version="v1",
        proof_timestamp_ms=1000,
        current_timestamp_ms=1600, # age 600 > 500
        timestamp_max_age_ms=500,
        proof_sensor_snapshot={},
        current_sensor_snapshot={},
        divergence_thresholds=[]
    )
    assert res is False
    assert err == "INTEGRITY_TIMESTAMP_EXPIRED"

def test_integrity_sensor_divergence_absolute():
    dt = DivergenceThreshold(sensor_type="a", method="absolute", max_divergence=5.0)
    
    # Pass (diff 2)
    res, err = check_integrity(
        "v1", "v1", 1000, 1100, 500,
        {"a": 10}, {"a": 12}, [dt]
    )
    assert res is True
    
    # Fail (diff 6)
    res, err = check_integrity(
        "v1", "v1", 1000, 1100, 500,
        {"a": 10}, {"a": 16}, [dt]
    )
    assert res is False
    assert err == "INTEGRITY_SENSOR_DIVERGENCE"

def test_integrity_sensor_divergence_percentage():
    dt = DivergenceThreshold(sensor_type="a", method="percentage", max_divergence=10.0) # 10%
    
    # Pass (10 -> 11 is 10%)
    res, err = check_integrity(
        "v1", "v1", 1000, 1100, 500,
        {"a": 100}, {"a": 110}, [dt]
    )
    # 110-100 = 10. 10/100 = 10%. <= 10%. Pass.
    assert res is True
    
    # Fail (100 -> 111 is 11%)
    res, err = check_integrity(
        "v1", "v1", 1000, 1100, 500,
        {"a": 100}, {"a": 111}, [dt]
    )
    assert res is False

def test_integrity_multiple_thresholds():
    dt1 = DivergenceThreshold(sensor_type="a", method="absolute", max_divergence=1.0)
    dt2 = DivergenceThreshold(sensor_type="b", method="absolute", max_divergence=1.0)
    
    # Fail second
    res, err = check_integrity(
        "v1", "v1", 1000, 1100, 500,
        {"a": 10, "b": 10}, {"a": 10, "b": 12}, [dt1, dt2]
    )
    assert res is False
    assert err == "INTEGRITY_SENSOR_DIVERGENCE"

def test_sensor_hash_mismatch_detected():
    """
    TOCTOU L1: Sensor hash mismatch simulation.
    Since check_integrity checks values, not hashes, we simulate the condition
    where hash mismatch would trigger this check.
    If values differ significantly (causing hash mismatch), check_integrity should catch it.
    """
    dt = DivergenceThreshold(sensor_type="temp", method="absolute", max_divergence=2.0)
    
    # Case 1: Hash mismatch (values differ) but within threshold -> Pass
    # proof: 50.0, current: 51.0 (diff 1.0 < 2.0)
    res, err = check_integrity(
        "v1", "v1", 1000, 1100, 500,
        {"temp": 50.0}, {"temp": 51.0}, [dt]
    )
    assert res is True
    
    # Case 2: Hash mismatch (values differ) and exceed threshold -> Fail
    # proof: 50.0, current: 53.0 (diff 3.0 > 2.0)
    res, err = check_integrity(
        "v1", "v1", 1000, 1100, 500,
        {"temp": 50.0}, {"temp": 53.0}, [dt]
    )
    assert res is False
    assert err == "INTEGRITY_SENSOR_DIVERGENCE"

