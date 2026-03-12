import pytest
import time
from pcag.core.services.tx_state_machine import TxStateMachine

class MockTime:
    def __init__(self):
        self._t = 1000.0 # ms
        
    def get_time(self):
        return self._t
        
    def advance(self, ms):
        self._t += ms

def test_happy_path():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    # Prepare
    res = tsm.prepare("tx1", "asset1", 500)
    assert res["status"] == "LOCK_GRANTED"
    
    # Commit
    res = tsm.commit("tx1", "asset1")
    assert res["status"] == "COMMITTED"
    
    # Verify lock released (another tx can acquire)
    res = tsm.prepare("tx2", "asset1", 500)
    assert res["status"] == "LOCK_GRANTED"

def test_lock_conflict():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    tsm.prepare("tx1", "asset1", 500)
    
    # Different tx
    res = tsm.prepare("tx2", "asset1", 500)
    assert res["status"] == "LOCK_DENIED"

def test_idempotent_prepare():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    tsm.prepare("tx1", "asset1", 500)
    res = tsm.prepare("tx1", "asset1", 500)
    assert res["status"] == "LOCK_GRANTED"

def test_idempotent_commit():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    tsm.prepare("tx1", "asset1", 500)
    tsm.commit("tx1", "asset1")
    
    res = tsm.commit("tx1", "asset1")
    assert res["status"] == "ALREADY_COMMITTED"

def test_abort():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    tsm.prepare("tx1", "asset1", 500)
    res = tsm.abort("tx1", "asset1")
    assert res["status"] == "ABORTED"
    
    # Lock should be released
    res = tsm.prepare("tx2", "asset1", 500)
    assert res["status"] == "LOCK_GRANTED"

def test_already_aborted():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    tsm.prepare("tx1", "asset1", 500)
    tsm.abort("tx1", "asset1")
    res = tsm.abort("tx1", "asset1")
    assert res["status"] == "ALREADY_ABORTED"

def test_estop():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    tsm.prepare("tx1", "asset1", 500)
    
    # ESTOP
    res = tsm.estop("asset1")
    assert res["status"] == "ESTOP_EXECUTED"
    
    # Lock gone
    res = tsm.prepare("tx2", "asset1", 500)
    assert res["status"] == "LOCK_GRANTED"

def test_lock_ttl_expiry():
    tm = MockTime()
    tsm = TxStateMachine(time_provider=tm.get_time)
    
    tsm.prepare("tx1", "asset1", 100) # 100ms TTL
    
    # Wait 150ms
    tm.advance(150)
    
    # New tx should succeed
    res = tsm.prepare("tx2", "asset1", 500)
    assert res["status"] == "LOCK_GRANTED"
    
    # Old tx cannot commit (lock lost)
    res = tsm.commit("tx1", "asset1")
    assert res["status"] == "ERROR" # Lock expired or lost
