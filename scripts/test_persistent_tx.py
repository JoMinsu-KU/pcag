import os
import sys
import logging

# Set up environment for testing
os.environ["PCAG_DATABASE_URL"] = "sqlite:///:memory:"

# Add project root to path
sys.path.append(os.getcwd())

from pcag.core.database.engine import init_db, SessionLocal
from pcag.apps.ot_interface.service import PersistentTxStateMachine
from pcag.core.database.models import TransactionRecord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_persistent_sm():
    logger.info("Initializing DB...")
    init_db()
    
    sm = PersistentTxStateMachine()
    
    tx1 = "tx-1001"
    asset1 = "robot-arm-1"
    
    logger.info(f"--- Scenario 1: Basic Success Flow ---")
    # 1. Prepare
    res = sm.prepare(tx1, asset1, 5000)
    logger.info(f"Prepare Tx1: {res}")
    assert res["status"] == "LOCK_GRANTED"
    
    # Verify in DB
    with SessionLocal() as session:
        tx_rec = session.get(TransactionRecord, tx1)
        assert tx_rec is not None
        assert tx_rec.status == "LOCKED"
        logger.info(f"DB Check: Tx1 is LOCKED")

    # 2. Commit
    res = sm.commit(tx1, asset1)
    logger.info(f"Commit Tx1: {res}")
    assert res["status"] == "COMMITTED"
    
    # Verify in DB
    with SessionLocal() as session:
        tx_rec = session.get(TransactionRecord, tx1)
        assert tx_rec.status == "COMMITTED"
        logger.info(f"DB Check: Tx1 is COMMITTED")

    logger.info(f"--- Scenario 2: Locking Conflict ---")
    tx2 = "tx-2001"
    tx3 = "tx-2002"
    asset2 = "conveyor-1"
    
    # Tx2 takes lock
    res = sm.prepare(tx2, asset2, 5000)
    assert res["status"] == "LOCK_GRANTED"
    
    # Tx3 tries to take same lock
    res = sm.prepare(tx3, asset2, 5000)
    logger.info(f"Prepare Tx3 (expect fail): {res}")
    assert res["status"] == "LOCK_DENIED"
    
    # Tx2 extends lock (Idempotency)
    res = sm.prepare(tx2, asset2, 10000)
    logger.info(f"Prepare Tx2 again (extend): {res}")
    assert res["status"] == "LOCK_GRANTED"
    
    # Tx2 Aborts
    res = sm.abort(tx2, asset2)
    logger.info(f"Abort Tx2: {res}")
    assert res["status"] == "ABORTED"
    
    # Now Tx3 can take lock
    res = sm.prepare(tx3, asset2, 5000)
    logger.info(f"Prepare Tx3 (retry): {res}")
    assert res["status"] == "LOCK_GRANTED"

    logger.info(f"--- Scenario 3: E-Stop ---")
    tx4 = "tx-3001"
    asset3 = "heater-1"
    
    sm.prepare(tx4, asset3, 5000)
    
    res = sm.estop(asset3)
    logger.info(f"E-Stop Asset3: {res}")
    assert res["status"] == "ESTOP_EXECUTED"
    
    # Verify Tx4 is ABORTED
    with SessionLocal() as session:
        tx_rec = session.get(TransactionRecord, tx4)
        assert tx_rec.status == "ABORTED"
        logger.info(f"DB Check: Tx4 is ABORTED by E-Stop")

    logger.info("All tests passed!")

if __name__ == "__main__":
    try:
        test_persistent_sm()
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)
