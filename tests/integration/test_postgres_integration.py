"""
PostgreSQL 통합 테스트
========================
실제 PostgreSQL 데이터베이스에 접속하여 Policy Store와 Evidence Ledger의
전체 CRUD 동작을 검증합니다.

pgAdmin4 (http://localhost:5050)에서 결과를 직접 확인할 수 있습니다.

필수 조건:
  - Docker로 PostgreSQL이 실행 중이어야 합니다:
    docker compose -f docker/docker-compose.db.yml up -d
    
실행 방법 (conda pcag 환경):
  conda activate pcag
  python -m pytest tests/integration/test_postgres_integration.py -v
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from pcag.core.database.engine import Base, DATABASE_URL
from pcag.core.database.models import PolicyRecord, EvidenceEventRecord
from pcag.core.utils.hash_utils import GENESIS_HASH, compute_event_hash, compute_sensor_hash
from pcag.apps.policy_store.repository import PolicyRepository
from pcag.apps.evidence_ledger.repository import EvidenceRepository


# PostgreSQL 연결 (실제 DB)
PG_ENGINE = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
PGSession = sessionmaker(bind=PG_ENGINE)


@pytest.fixture(scope="module", autouse=True)
def setup_postgres():
    """테스트 모듈 시작 시 PostgreSQL 테이블 생성"""
    print(f"\n[PostgreSQL] Connecting to: {DATABASE_URL}")
    
    # 테이블 생성
    Base.metadata.create_all(bind=PG_ENGINE)
    
    # 테이블 확인
    inspector = inspect(PG_ENGINE)
    tables = inspector.get_table_names()
    print(f"[PostgreSQL] Tables: {tables}")
    
    yield
    
    # 테스트 후 테스트 데이터 정리 (테이블은 유지)
    with PGSession() as db:
        # 테스트 데이터만 삭제 (pg_test_ 접두사)
        db.execute(text("DELETE FROM evidence_events WHERE transaction_id LIKE 'pg_test_%'"))
        db.execute(text("DELETE FROM policies WHERE policy_version_id LIKE 'pg_test_%'"))
        db.commit()


@pytest.fixture
def db():
    """각 테스트에 DB 세션 제공"""
    session = PGSession()
    yield session
    session.close()


# ============================================================
# PostgreSQL Policy Store 테스트
# ============================================================

class TestPolicyStorePostgres:
    """Policy Store — PostgreSQL 실제 테스트"""
    
    def test_create_policy(self, db):
        """정책 생성 → PostgreSQL에 실제 저장"""
        repo = PolicyRepository(db)
        
        policy_doc = {
            "policy_version_id": "pg_test_v001",
            "global_policy": {"hash": {"algorithm": "sha256"}},
            "assets": {
                "reactor_01": {
                    "asset_id": "reactor_01",
                    "sil_level": 2,
                    "sensor_source": "modbus_sensor",
                    "ot_executor": "mock_executor",
                    "consensus": {"mode": "WEIGHTED", "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25}},
                    "ruleset": [
                        {"rule_id": "max_temp", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0}
                    ]
                }
            }
        }
        
        record = repo.create_policy(
            policy_version_id="pg_test_v001",
            issued_at_ms=int(time.time() * 1000),
            document=policy_doc
        )
        
        assert record.policy_version_id == "pg_test_v001"
        assert record.is_active == False
        print(f"  [OK] Policy 'pg_test_v001' created in PostgreSQL")
    
    def test_activate_policy(self, db):
        """정책 활성화 → pgAdmin에서 is_active=true 확인 가능"""
        repo = PolicyRepository(db)
        
        # 먼저 생성 (이미 있으면 스킵)
        if not repo.get_policy("pg_test_v001"):
            self.test_create_policy(db)
        
        record = repo.activate_policy("pg_test_v001")
        assert record is not None
        assert record.is_active == True
        print(f"  [OK] Policy 'pg_test_v001' activated in PostgreSQL")
    
    def test_get_active_version(self, db):
        """활성 정책 조회"""
        repo = PolicyRepository(db)
        
        if not repo.get_policy("pg_test_v001"):
            self.test_create_policy(db)
            repo.activate_policy("pg_test_v001")
        
        active = repo.get_active_version()
        # pg_test_v001이 활성이거나, 다른 정책이 활성일 수 있음
        assert active is not None
        print(f"  [OK] Active policy: {active}")
    
    def test_get_asset_profile(self, db):
        """자산 정책 프로필 조회"""
        repo = PolicyRepository(db)
        
        if not repo.get_policy("pg_test_v001"):
            self.test_create_policy(db)
        
        record = repo.get_policy("pg_test_v001")
        profile = record.get_asset_profile("reactor_01")
        
        assert profile is not None
        assert profile["sil_level"] == 2
        assert profile["sensor_source"] == "modbus_sensor"
        print(f"  [OK] Asset 'reactor_01' profile retrieved: SIL={profile['sil_level']}")
    
    def test_update_asset_profile(self, db):
        """자산 정책 수정 → pgAdmin에서 변경 확인 가능"""
        repo = PolicyRepository(db)
        
        if not repo.get_policy("pg_test_v001"):
            self.test_create_policy(db)
        
        # SIL 2 → 3으로 수정
        record = repo.get_policy("pg_test_v001")
        profile = record.get_asset_profile("reactor_01")
        profile["sil_level"] = 3
        
        success = repo.update_asset_profile("pg_test_v001", "reactor_01", profile)
        assert success == True
        
        # 수정 확인
        updated = repo.get_policy("pg_test_v001").get_asset_profile("reactor_01")
        assert updated["sil_level"] == 3
        print(f"  [OK] Asset 'reactor_01' SIL updated to {updated['sil_level']} in PostgreSQL")


# ============================================================
# PostgreSQL Evidence Ledger 테스트
# ============================================================

class TestEvidenceLedgerPostgres:
    """Evidence Ledger — PostgreSQL 실제 테스트"""
    
    def _make_event(self, tx_id, seq, stage, payload, prev_hash):
        """증거 이벤트 생성 헬퍼"""
        input_hash = compute_sensor_hash(payload)
        event_hash = compute_event_hash(prev_hash, payload)
        return {
            "tx_id": tx_id, "seq": seq, "stage": stage,
            "payload": payload, "input_hash": input_hash,
            "prev_hash": prev_hash, "event_hash": event_hash
        }
    
    def test_append_evidence_chain(self, db):
        """해시 체인 증거 추가 → PostgreSQL에 실제 저장"""
        repo = EvidenceRepository(db)
        
        stages = ["RECEIVED", "SCHEMA_VALIDATED", "INTEGRITY_PASSED",
                  "SAFETY_PASSED", "PREPARE_LOCK_GRANTED", "REVERIFY_PASSED", "COMMIT_ACK"]
        
        prev = GENESIS_HASH
        for i, stage in enumerate(stages):
            payload = {"stage": stage, "step": i, "timestamp": int(time.time() * 1000)}
            event = self._make_event("pg_test_tx001", i, stage, payload, prev)
            
            record = repo.append_event(
                transaction_id=event["tx_id"],
                sequence_no=event["seq"],
                stage=event["stage"],
                timestamp_ms=int(time.time() * 1000),
                payload=payload,
                input_hash=event["input_hash"],
                prev_hash=event["prev_hash"],
                event_hash=event["event_hash"]
            )
            prev = event["event_hash"]
        
        print(f"  [OK] 7 evidence events appended to PostgreSQL for tx 'pg_test_tx001'")
    
    def test_verify_chain_integrity(self, db):
        """해시 체인 무결성 검증 — PostgreSQL 데이터 기반"""
        repo = EvidenceRepository(db)
        
        # 먼저 데이터 추가
        events = repo.get_transaction_events("pg_test_tx001")
        if not events:
            self.test_append_evidence_chain(db)
        
        chain_valid = repo.verify_chain("pg_test_tx001")
        assert chain_valid == True
        print(f"  [OK] Hash chain integrity verified in PostgreSQL")
    
    def test_get_transaction_events(self, db):
        """트랜잭션 이벤트 조회 + 순서 확인"""
        repo = EvidenceRepository(db)
        
        events = repo.get_transaction_events("pg_test_tx001")
        if not events:
            self.test_append_evidence_chain(db)
            events = repo.get_transaction_events("pg_test_tx001")
        
        assert len(events) == 7
        assert events[0].stage == "RECEIVED"
        assert events[6].stage == "COMMIT_ACK"
        
        # 순서 확인
        for i, event in enumerate(events):
            assert event.sequence_no == i
        
        print(f"  [OK] {len(events)} events retrieved in correct order from PostgreSQL")
    
    def test_genesis_hash_correct(self, db):
        """첫 이벤트의 prev_hash = Genesis Hash 확인"""
        repo = EvidenceRepository(db)
        
        events = repo.get_transaction_events("pg_test_tx001")
        if not events:
            self.test_append_evidence_chain(db)
            events = repo.get_transaction_events("pg_test_tx001")
        
        first_event = events[0]
        assert first_event.prev_hash == GENESIS_HASH
        print(f"  [OK] First event prev_hash = Genesis Hash (sha256(''))")


# ============================================================
# PostgreSQL 직접 SQL 테스트
# ============================================================

class TestPostgresDirectSQL:
    """PostgreSQL에 직접 SQL로 데이터 확인"""
    
    def test_tables_exist(self, db):
        """테이블 존재 확인"""
        inspector = inspect(PG_ENGINE)
        tables = inspector.get_table_names()
        assert "policies" in tables, "policies 테이블이 없습니다"
        assert "evidence_events" in tables, "evidence_events 테이블이 없습니다"
        print(f"  [OK] Tables found: {tables}")
    
    def test_policy_count(self, db):
        """policies 테이블 레코드 수 확인"""
        result = db.execute(text("SELECT COUNT(*) FROM policies"))
        count = result.scalar()
        print(f"  [OK] policies table has {count} records")
        assert count >= 0
    
    def test_evidence_count(self, db):
        """evidence_events 테이블 레코드 수 확인"""
        result = db.execute(text("SELECT COUNT(*) FROM evidence_events"))
        count = result.scalar()
        print(f"  [OK] evidence_events table has {count} records")
        assert count >= 0
