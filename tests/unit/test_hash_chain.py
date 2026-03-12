import hashlib
from pcag.core.utils.hash_utils import compute_hash, compute_event_hash, compute_sensor_hash, GENESIS_HASH
from pcag.core.utils.canonicalize import canonicalize

def test_genesis_hash():
    """First prev_hash should be sha256 of empty string."""
    expected = hashlib.sha256(b"").hexdigest()
    assert GENESIS_HASH == expected

def test_event_hash_computation():
    """event_hash = sha256(prev_hash + canonical(payload))"""
    prev = GENESIS_HASH
    payload = {"action": "move", "val": 10}
    
    canonical_payload = canonicalize(payload)
    expected = hashlib.sha256((prev + canonical_payload).encode("utf-8")).hexdigest()
    
    assert compute_event_hash(prev, payload) == expected

def test_chain_continuity():
    """Each event's prev_hash should be the previous event's event_hash."""
    h0 = GENESIS_HASH
    p1 = {"step": 1}
    h1 = compute_event_hash(h0, p1)
    
    p2 = {"step": 2}
    h2 = compute_event_hash(h1, p2)
    
    # Manually verify h2
    c1 = canonicalize(p1)
    c2 = canonicalize(p2)
    
    calc_h1 = hashlib.sha256((h0 + c1).encode("utf-8")).hexdigest()
    calc_h2 = hashlib.sha256((calc_h1 + c2).encode("utf-8")).hexdigest()
    
    assert h1 == calc_h1
    assert h2 == calc_h2

def test_tamper_detection():
    """Modifying any event should break the chain."""
    h0 = GENESIS_HASH
    p1 = {"step": 1}
    h1 = compute_event_hash(h0, p1)
    
    # Tamper with p1
    p1_tampered = {"step": 1, "malicious": True}
    h1_tampered = compute_event_hash(h0, p1_tampered)
    
    assert h1 != h1_tampered

def test_sensor_hash_deterministic():
    """Same sensor data should always produce the same hash."""
    s1 = {"temp": 25.5, "pressure": 101.3}
    s2 = {"pressure": 101.3, "temp": 25.5}
    
    assert compute_sensor_hash(s1) == compute_sensor_hash(s2)
