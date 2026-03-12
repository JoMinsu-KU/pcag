"""
Isaac Sim Proxy — Worker 프로세스와 Queue 통신
================================================
ISimulationBackend 인터페이스를 구현하되,
실제 시뮬레이션은 별도 프로세스(isaac_worker)에서 실행됩니다.

Safety Cluster(uvicorn)에서 사용:
  proxy = IsaacSimProxy()
  proxy.start(config)
  result = proxy.validate_trajectory(...)
  proxy.stop()
"""
import os
import uuid
import time
import logging
import multiprocessing as mp
from pcag.core.ports.simulation_backend import ISimulationBackend

logger = logging.getLogger(__name__)


class IsaacSimProxy(ISimulationBackend):
    """
    Isaac Sim Worker 프로세스와 Queue로 통신하는 프록시
    
    ISimulationBackend 인터페이스를 구현하여,
    Safety Cluster의 service.py에서는 다른 백엔드와 동일하게 사용됩니다.
    """
    
    def __init__(self):
        self._enabled = os.environ.get("PCAG_ENABLE_ISAAC", "false").lower() == "true"
        self._proc = None
        self._req_q = None
        self._res_q = None
        self._initialized = False
        self._timeout_s = 30
    
    def is_initialized(self) -> bool:
        """Worker 프로세스가 실행 중이고 준비되었는지"""
        return self._initialized and self._proc is not None and self._proc.is_alive()
    
    def initialize(self, config: dict) -> None:
        """
        Isaac Sim Worker 프로세스 시작
        
        메인 프로세스에서 호출. Worker는 별도 프로세스에서 Isaac Sim을 실행합니다.
        """
        if self._initialized:
            logger.info("Isaac Sim Proxy already initialized")
            return
        
        if not self._enabled:
            logger.info("Isaac Sim disabled (PCAG_ENABLE_ISAAC != true)")
            return
        
        self._timeout_s = config.get("timeout_ms", 30000) / 1000
        
        logger.info("Starting Isaac Sim Worker process...")
        
        # Windows에서는 spawn 컨텍스트 명시
        ctx = mp.get_context("spawn")
        self._req_q = ctx.Queue()
        self._res_q = ctx.Queue()
        
        # Worker 프로세스 시작
        self._proc = ctx.Process(
            target=self._worker_entry,
            args=(self._req_q, self._res_q, config),
            daemon=True
        )
        self._proc.start()
        
        # 부팅 완료 대기 (최대 120초 — Isaac Sim 초기화 시간)
        try:
            boot_msg = self._res_q.get(timeout=120)
            if boot_msg.get("ok"):
                self._initialized = True
                logger.info(f"Isaac Sim Worker ready: {boot_msg.get('message')}")
            else:
                logger.error(f"Isaac Sim Worker boot failed: {boot_msg.get('error')}")
                self._cleanup()
        except Exception as e:
            logger.error(f"Isaac Sim Worker boot timeout: {e}")
            self._cleanup()
    
    @staticmethod
    def _worker_entry(req_q, res_q, config):
        """Worker 프로세스 진입점 (static method for pickling)"""
        from pcag.apps.safety_cluster.isaac_worker import isaac_worker_main
        isaac_worker_main(req_q, res_q, config)
    
    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict
    ) -> dict:
        """
        Isaac Sim Worker에 검증 요청 전송 + 결과 수신
        
        Worker가 없거나 응답 없으면 INDETERMINATE 반환.
        """
        if not self.is_initialized():
            return {
                "verdict": "INDETERMINATE",
                "engine": "isaac_sim",
                "common": {"first_violation_step": None, "violated_constraint": None, "latency_ms": 0, "steps_completed": 0},
                "details": {"reason": "Isaac Sim Worker not available"}
            }
        
        job_id = uuid.uuid4().hex
        
        # 요청 전송
        self._req_q.put({
            "job_id": job_id,
            "state": current_state,
            "actions": action_sequence,
            "constraints": constraints,
            "world_ref": constraints.get("world_ref")
        })
        
        # 결과 대기
        try:
            msg = self._res_q.get(timeout=self._timeout_s)
            
            if msg.get("job_id") != job_id:
                logger.warning(f"Job ID mismatch: expected {job_id}, got {msg.get('job_id')}")
                # 일단 사용 (단일 요청 직렬 처리이므로 거의 발생 안 함)
            
            if msg.get("ok"):
                return msg["result"]
            else:
                logger.error(f"Isaac Worker error: {msg.get('error')}")
                return {
                    "verdict": "INDETERMINATE",
                    "engine": "isaac_sim",
                    "common": {"first_violation_step": None, "violated_constraint": None, "latency_ms": 0, "steps_completed": 0},
                    "details": {"reason": f"Worker error: {msg.get('error')}"}
                }
                
        except Exception as e:
            logger.error(f"Isaac Worker timeout/error: {e}")
            return {
                "verdict": "INDETERMINATE",
                "engine": "isaac_sim",
                "common": {"first_violation_step": None, "violated_constraint": None, "latency_ms": 0, "steps_completed": 0},
                "details": {"reason": f"Worker communication error: {str(e)}"}
            }
    
    def get_current_state(self) -> dict:
        """현재 시뮬레이션(Digital Twin) 상태 조회"""
        if not self.is_initialized():
            return {}
        
        job_id = uuid.uuid4().hex
        
        try:
            self._req_q.put({
                "type": "GET_STATE",
                "job_id": job_id
            })
            
            # State query should be fast
            msg = self._res_q.get(timeout=5.0)
            
            if msg.get("job_id") == job_id and msg.get("ok"):
                return msg["result"]
            else:
                logger.error(f"GET_STATE failed: {msg.get('error')}")
                return {}
                
        except Exception as e:
            logger.error(f"GET_STATE timeout/error: {e}")
            return {}

    def shutdown(self) -> None:
        """Worker 프로세스 종료"""
        logger.info("Shutting down Isaac Sim Proxy...")
        if self._proc and self._proc.is_alive():
            try:
                self._req_q.put({"type": "SHUTDOWN"})
                self._proc.join(timeout=15)
                if self._proc.is_alive():
                    self._proc.terminate()
                    logger.warning("Isaac Worker terminated forcefully")
            except Exception as e:
                logger.error(f"Worker shutdown error: {e}")
        
        self._cleanup()
        logger.info("Isaac Sim Proxy shutdown complete")
    
    def _cleanup(self):
        """리소스 정리"""
        self._proc = None
        self._req_q = None
        self._res_q = None
        self._initialized = False
