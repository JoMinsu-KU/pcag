"""Revision dispatch ownership tests on isolated SQLite, never the live plant DB.

PostgreSQL uses the same PK/conditional UPSERT/CAS strategy. A separate live
revision suite is required for PostgreSQL process-restart/network experiments.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.orm import sessionmaker

from pcag.core.database.engine import Base
from pcag.core.database.models import AssetExecutionLockRecord, OperationReceiptRecord, TransactionRecord
from pcag.apps.ot_interface.service import PersistentTxStateMachine, compute_operation_digest
from pcag.apps.ot_interface import routes
from pcag.core.middleware import auth

ACTION = [{"action_type":"move_to", "params":{"target_x":1.000001,"target_y":2}}]


@pytest.fixture
def store(tmp_path):
    postgres_url = os.environ.get("PCAG_REVISION_TEST_DATABASE_URL")
    schema = None
    if postgres_url:
        parsed = make_url(postgres_url)
        if parsed.get_backend_name() != 'postgresql' or 'revision' not in (parsed.database or '').lower():
            pytest.fail('Protocol tests require a dedicated PostgreSQL database whose name contains revision')
        schema = 'pcag_revision_test_' + uuid.uuid4().hex
        control = create_engine(postgres_url)
        with control.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = control.execution_options(schema_translate_map={None:schema})
    else:
        engine = create_engine(f"sqlite:///{(tmp_path/'operations.db').as_posix()}",
                               connect_args={"check_same_thread":False,"timeout":30})
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    clock = [1000]
    machine = PersistentTxStateMachine(sessions, lambda:clock[0])
    yield machine, sessions, clock
    engine.dispose()
    if schema is not None:
        # This name was generated above; no user-provided schema is dropped.
        with control.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        control.dispose()


def completed(tx="op", asset="agv_01"):
    return {"status":"COMPLETED", "transaction_id":tx,"asset_id":asset,
            "accepted":True,"completed":True,"execution_confirmed":True,
            "ack_boundary":"test_executor_completed",
            "payload_digest":compute_operation_digest(asset,ACTION)}


def claim(machine,tx="op",asset="agv_01"):
    assert machine.prepare(tx,asset,1000,ACTION)["status"] == "LOCK_GRANTED"
    result=machine.claim_commit(tx,asset,ACTION)
    assert result["status"] == "READY"
    return result


def test_legacy_prepare_binds_first_commit_and_replays_durable_receipt(store):
    machine,sessions,_=store
    assert machine.prepare("op","agv_01",1000)["status"] == "LOCK_GRANTED"
    ownership=machine.claim_commit("op","agv_01",ACTION)
    assert ownership["status"] == "READY"
    result=machine.finalize_commit("op","agv_01",claim_token=ownership["claim_token"],executor_receipt=completed())
    assert result["operation_state"] == "COMPLETED"
    restarted=PersistentTxStateMachine(sessions)
    replay=restarted.claim_commit("op","agv_01",ACTION)
    assert replay["status"] == "ALREADY_COMMITTED"
    assert replay["dispatch_count"] == 1
    assert replay["receipt"]["ack_boundary"] == "test_executor_completed"


def test_digest_does_not_round_action_values_and_payload_conflict_is_rejected(store):
    machine,_,_=store
    different=[{"action_type":"move_to","params":{"target_x":1.000002,"target_y":2}}]
    assert compute_operation_digest("agv_01",ACTION)!=compute_operation_digest("agv_01",different)
    assert machine.prepare("op","agv_01",1000,ACTION)["status"] == "LOCK_GRANTED"
    assert machine.prepare("op","agv_01",1000,different)["reason"] == "PAYLOAD_CONFLICT"
    assert machine.claim_commit("op","agv_01",different)["reason"] == "PAYLOAD_CONFLICT"
    assert machine.prepare("op","other_asset",1000,ACTION)["reason"] == "ASSET_MISMATCH"


def test_simultaneous_prepares_have_only_one_asset_owner(store):
    machine,sessions,_=store
    count=int(os.environ.get('PCAG_REVISION_CONCURRENCY','8'))
    barrier=threading.Barrier(count)
    def run(i):
        barrier.wait()
        return machine.prepare(f"op-{i}","agv_01",1000,ACTION)
    with ThreadPoolExecutor(max_workers=count) as pool:
        results=list(pool.map(run,range(count)))
    assert sum(r["status"] == "LOCK_GRANTED" for r in results)==1
    with sessions() as db:
        slots=db.execute(select(AssetExecutionLockRecord)).scalars().all()
        assert len(slots)==1 and slots[0].phase=="RESERVED"


def test_simultaneous_commit_claims_have_one_dispatch_winner(store):
    machine,_,_=store
    assert machine.prepare("op","agv_01",1000,ACTION)["status"] == "LOCK_GRANTED"
    count=int(os.environ.get('PCAG_REVISION_CONCURRENCY','16'))
    barrier=threading.Barrier(count)
    def run(_):
        barrier.wait()
        return machine.claim_commit("op","agv_01",ACTION)
    with ThreadPoolExecutor(max_workers=count) as pool:
        results=list(pool.map(run,range(count)))
    assert sum(r["status"]=="READY" for r in results)==1
    assert machine.get_operation_status("op")["dispatch_count"]==1


def test_expired_owner_is_fenced_and_cannot_release_new_owner(store):
    machine,_,clock=store
    first=machine.prepare("old","agv_01",10,ACTION)
    clock[0]=1010
    second=machine.prepare("new","agv_01",1000,ACTION)
    assert second["status"]=="LOCK_GRANTED" and second["lock_token"]>first["lock_token"]
    assert machine.claim_commit("old","agv_01",ACTION,lock_token=first["lock_token"])["status"]=="TIMEOUT"
    assert machine.abort("old","agv_01")["status"]=="ABORTED"
    assert machine.claim_commit("new","agv_01",ACTION,lock_token=second["lock_token"])["status"]=="READY"


def test_unknown_is_quarantined_across_expiry_retry_abort_and_reset(store):
    machine,_,clock=store
    ownership=claim(machine)
    assert machine.mark_unknown("op","agv_01","ACK lost",claim_token=ownership["claim_token"])["status"]=="UNKNOWN"
    clock[0]=1_000_000
    assert machine.prepare("other","agv_01",1000,ACTION)["status"]=="LOCK_DENIED"
    assert machine.claim_commit("op","agv_01",ACTION)["status"]=="UNKNOWN"
    assert machine.abort("op","agv_01")["status"]=="ABORT_REJECTED"
    assert machine.reset_prepared_asset("agv_01","test reset")["status"]=="RESET_REJECTED"
    assert machine.reconcile("op","agv_01",{"status":"NOT_FOUND"})["status"]=="UNKNOWN"
    assert machine.get_operation_status("op")["dispatch_count"]==1
    assert machine.reconcile("op","agv_01",completed())["status"]=="COMMITTED"
    assert machine.prepare("other","agv_01",1000,ACTION)["status"]=="LOCK_GRANTED"


def test_reconciliation_rejects_identity_or_payload_conflicts(store):
    machine,_,_=store
    own=claim(machine)
    machine.mark_unknown("op","agv_01","ACK lost",claim_token=own["claim_token"])
    wrong={**completed(),"payload_digest":"0"*64}
    assert machine.reconcile("op","agv_01",wrong)["status"]=="UNKNOWN"
    assert machine.get_operation_status("op")["operation_state"]=="UNKNOWN"
    wrong={**completed(),"transaction_id":"wrong"}
    assert machine.reconcile("op","agv_01",wrong)["status"]=="UNKNOWN"


def test_acceptance_is_not_completion_and_receipt_can_be_reconciled(store):
    machine,_,_=store
    own=claim(machine)
    receipt={**completed(),"status":"ACCEPTED","completed":False,"ack_boundary":"durable_acceptance"}
    result=machine.finalize_commit("op","agv_01",claim_token=own["claim_token"],executor_receipt=receipt)
    assert result["operation_state"]=="ACCEPTED" and result["completed"] is False
    assert result["completed_at_ms"] is None
    assert machine.reset_prepared_asset("agv_01","test")["status"]=="RESET_REJECTED"
    assert machine.reconcile("op","agv_01",completed())["operation_state"]=="COMPLETED"


def test_claim_token_required_to_finalize(store):
    machine,_,_=store
    claim(machine)
    assert machine.finalize_commit("op","agv_01",executor_receipt=completed())["status"]=="REJECTED"
    assert machine.finalize_commit("op","agv_01",claim_token="wrong",executor_receipt=completed())["status"]=="REJECTED"


def test_receipt_write_failure_does_not_allow_redispatch(store,monkeypatch):
    machine,sessions,_=store
    own=claim(machine)
    from pcag.apps.ot_interface.repository import TxRepository
    original=TxRepository.transition_operation
    def failing(self,transaction_id,states,values,**kwargs):
        if values.get("state")=="COMPLETED":
            raise RuntimeError("injected receipt storage failure")
        return original(self,transaction_id,states,values,**kwargs)
    with monkeypatch.context() as m:
        m.setattr(TxRepository,"transition_operation",failing)
        result=machine.finalize_commit("op","agv_01",claim_token=own["claim_token"],executor_receipt=completed())
        assert result["status"]=="UNKNOWN"
    restarted=PersistentTxStateMachine(sessions)
    assert restarted.claim_commit("op","agv_01",ACTION)["status"]=="IN_PROGRESS"
    assert restarted.reconcile("op","agv_01",completed())["operation_state"]=="COMPLETED"


def test_additive_schema_preserves_legacy_rows_without_redispatch(tmp_path):
    engine=create_engine(f"sqlite:///{(tmp_path/'legacy.db').as_posix()}")
    TransactionRecord.__table__.create(engine)
    sessions=sessionmaker(bind=engine)
    with sessions.begin() as db:
        db.add(TransactionRecord(transaction_id="old",asset_id="agv_01",status="COMMITTED"))
    Base.metadata.create_all(engine)
    machine=PersistentTxStateMachine(sessions)
    assert machine.claim_direct("old","agv_01",ACTION)["status"]=="REJECTED"
    assert machine.prepare("old","agv_01",1000,ACTION)["status"]=="PREPARE_REJECTED"
    with sessions() as db:
        assert db.get(TransactionRecord,"old").status=="COMMITTED"
    engine.dispose()


@pytest.fixture
def api(store,monkeypatch):
    machine,_,_=store
    monkeypatch.setattr(routes,"_state_machine",machine)
    monkeypatch.setattr(auth,"_get_auth_config",lambda:{"enabled":True,"api_keys":["revision-test-key"]})
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as client:
        yield client,machine


def test_lost_executor_ack_is_reconciled_without_second_effect(api,monkeypatch):
    client,machine=api
    class Executor:
        count=0
        def execute(self,**kwargs):
            self.count+=1
            self.receipt=completed(kwargs["transaction_id"],kwargs["asset_id"])
            raise TimeoutError("ACK dropped after the effect")
        def query_operation(self,**kwargs):return self.receipt
        def safe_state(self,asset_id):return True
    executor=Executor()
    monkeypatch.setattr(routes.ExecutorManager,"get_executor",lambda _:executor)
    payload={"transaction_id":"op","asset_id":"agv_01","action_sequence":ACTION}
    assert client.post('/v1/prepare',json={**payload,"lock_ttl_ms":1000}).json()['status']=='LOCK_GRANTED'
    assert client.post('/v1/commit',json=payload).json()['status']=='UNKNOWN'
    assert client.post('/v1/commit',json=payload).json()['status']=='UNKNOWN'
    assert executor.count==1
    assert client.post('/v1/reconcile',json={"transaction_id":"op","asset_id":"agv_01"}).json()['status']=='COMMITTED'
    assert client.post('/v1/commit',json=payload).json()['status']=='ALREADY_COMMITTED'
    assert executor.count==1


def test_concurrent_http_commit_dispatches_one_effect(api,monkeypatch):
    client,machine=api
    entered,released=threading.Event(),threading.Event()
    class Executor:
        count=0
        def execute(self,**kwargs):
            self.count+=1;entered.set();released.wait(10)
            return completed(kwargs['transaction_id'],kwargs['asset_id'])
        def safe_state(self,asset_id):return True
    executor=Executor()
    monkeypatch.setattr(routes.ExecutorManager,'get_executor',lambda _:executor)
    claim_payload={'transaction_id':'op','asset_id':'agv_01','action_sequence':ACTION}
    assert client.post('/v1/prepare',json={**claim_payload,'lock_ttl_ms':1000}).json()['status']=='LOCK_GRANTED'
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(client.post,'/v1/commit',json=claim_payload)
        assert entered.wait(5)
        duplicate=client.post('/v1/commit',json=claim_payload)
        assert duplicate.json()['status']=='IN_PROGRESS'
        released.set()
        assert pending.result(timeout=10).json()['status']=='ACK'
    assert executor.count==1


def test_revision_reset_is_gated_and_never_clears_unknown(api,monkeypatch):
    client,machine=api
    headers={'X-API-Key':'revision-test-key'}
    monkeypatch.delenv('PCAG_REVISION_MODE',raising=False)
    assert client.get('/v1/revision/state',headers=headers).status_code==404
    monkeypatch.setenv('PCAG_REVISION_MODE','true')
    assert client.get('/v1/revision/state').status_code==401
    assert machine.prepare('op','agv_01',1000,ACTION)['status']=='LOCK_GRANTED'
    assert client.post('/v1/revision/reset',json={'asset_id':'agv_01','reason':'isolated test'},headers=headers).status_code==200
    own=claim(machine,'other')
    machine.mark_unknown('other','agv_01','lost',claim_token=own['claim_token'])
    assert client.post('/v1/revision/reset',json={'asset_id':'agv_01','reason':'isolated test'},headers=headers).status_code==409


def test_direct_revision_bypasses_asset_admission_but_keeps_identity(api,monkeypatch):
    client,machine=api
    monkeypatch.setenv('PCAG_REVISION_MODE','true')
    class Executor:
        count=0
        def execute(self,**kwargs):
            self.count+=1;return completed(kwargs['transaction_id'],kwargs['asset_id'])
    executor=Executor()
    monkeypatch.setattr(routes.ExecutorManager,'get_executor',lambda _:executor)
    assert machine.prepare('reservation','agv_01',1000,ACTION)['status']=='LOCK_GRANTED'
    payload={'transaction_id':'direct','asset_id':'agv_01','action_sequence':ACTION}
    headers={'X-API-Key':'revision-test-key'}
    assert client.post('/v1/revision/direct-execute',json=payload,headers=headers).json()['status']=='ACK'
    assert client.post('/v1/revision/direct-execute',json=payload,headers=headers).json()['status']=='ALREADY_COMMITTED'
    assert executor.count==1
    assert machine.get_operation_status('reservation')['operation_state']=='PREPARED'


def test_duplicate_prepare_renews_same_fence_without_second_operation(store):
    machine,sessions,clock=store
    first=machine.prepare('op','agv_01',1000,ACTION)
    clock[0]+=100
    repeated=machine.prepare('op','agv_01',1000,ACTION)
    assert first['lock_token']==repeated['lock_token']
    assert repeated['lock_expires_at_ms']==2100
    with sessions() as db:
        assert len(db.execute(select(OperationReceiptRecord)).scalars().all())==1


def test_distinct_operation_ids_allow_same_payload_without_false_dedup(store):
    machine,_,_=store
    for tx in ['first','next_cycle']:
        own=claim(machine,tx)
        assert machine.finalize_commit(tx,'agv_01',claim_token=own['claim_token'],executor_receipt=completed(tx))['status']=='COMMITTED'
    assert machine.get_operation_status('first')['dispatch_count']==1
    assert machine.get_operation_status('next_cycle')['dispatch_count']==1


def test_unknown_cas_miss_cannot_overwrite_legacy_status_or_quarantine(store, monkeypatch):
    machine,sessions,_=store
    ownership=claim(machine)
    from pcag.apps.ot_interface.repository import TxRepository
    original=TxRepository.transition_operation
    def lose_unknown_cas(repo, transaction_id, states, values, **kwargs):
        if values.get('state') == 'UNKNOWN':
            return 0
        return original(repo,transaction_id,states,values,**kwargs)
    monkeypatch.setattr(TxRepository,'transition_operation',lose_unknown_cas)
    result=machine.mark_unknown('op','agv_01','injected CAS race',claim_token=ownership['claim_token'])
    assert result['operation_state']=='DISPATCHING'
    with sessions() as session:
        assert session.get(TransactionRecord,'op').status=='DISPATCHING'
        assert session.get(AssetExecutionLockRecord,'agv_01').phase=='DISPATCHING'


def test_contradictory_completion_receipt_cannot_release_dispatch_ownership(store):
    machine,sessions,_=store
    ownership=claim(machine)
    receipt={**completed(),'completed':False}
    result=machine.finalize_commit('op','agv_01',claim_token=ownership['claim_token'],executor_receipt=receipt)
    assert result['status']=='UNKNOWN'
    assert result['reason']=='CONTRADICTORY_EXECUTOR_RECEIPT'
    assert machine.claim_commit('op','agv_01',ACTION)['status']=='IN_PROGRESS'
    assert machine.prepare('new_operation','agv_01',1000,ACTION)['status']=='LOCK_DENIED'


def test_actual_ot_process_exit_after_model_effect_does_not_redispatch(store,tmp_path):
    import sqlite3
    import subprocess
    import sys
    machine,sessions,_=store
    assert machine.prepare('op','agv_01',1000,ACTION)['status']=='LOCK_GRANTED'
    journal=tmp_path/'independent_executor_effects.db'
    child_env=os.environ.copy()
    engine=sessions.kw['bind']
    child_env['PCAG_CHILD_DB_URL']=engine.url.render_as_string(hide_password=False)
    child_env['PCAG_CHILD_SCHEMA']=engine.get_execution_options().get('schema_translate_map',{}).get(None,'')
    child_env['PCAG_CHILD_JOURNAL']=str(journal)
    code='''
import os, sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pcag.apps.ot_interface.service import PersistentTxStateMachine
engine=create_engine(os.environ['PCAG_CHILD_DB_URL'])
schema=os.environ.get('PCAG_CHILD_SCHEMA')
if schema: engine=engine.execution_options(schema_translate_map={None:schema})
machine=PersistentTxStateMachine(sessionmaker(bind=engine),lambda:1000)
actions=[{'action_type':'move_to','params':{'target_x':1.000001,'target_y':2}}]
assert machine.claim_commit('op','agv_01',actions)['status']=='READY'
# Independent executor model commits an observed effect before the OT owner exits.
with sqlite3.connect(os.environ['PCAG_CHILD_JOURNAL']) as db:
 db.execute('CREATE TABLE effects(operation_id TEXT PRIMARY KEY, effect_count INTEGER NOT NULL)')
 db.execute('INSERT INTO effects VALUES (?,?)',('op',1))
os._exit(23)
'''
    result=subprocess.run([sys.executable,'-c',code],env=child_env,capture_output=True,text=True,timeout=30)
    assert result.returncode==23,result.stderr
    recovered=PersistentTxStateMachine(sessions)
    assert recovered.claim_commit('op','agv_01',ACTION)['status']=='IN_PROGRESS'
    with sqlite3.connect(journal) as db:
        assert db.execute('SELECT effect_count FROM effects WHERE operation_id=?',('op',)).fetchone()[0]==1
    assert recovered.reconcile('op','agv_01',completed())['operation_state']=='COMPLETED'
    assert recovered.claim_commit('op','agv_01',ACTION)['status']=='ALREADY_COMMITTED'
